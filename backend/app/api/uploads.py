from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Analysis, TestIndicator, User
from ..schemas import UploadResponse
from ..services.normalization import compute_deviation
from ..services.ocr import extract_tests_from_pdf, extract_tests_from_text, mock_extract_tests, ocr_image_bytes, ocr_pdf_bytes
from ..services.storage import put_object
from .deps import get_current_user

router = APIRouter()


@router.post("/document", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # 1) сохраняем файл в MinIO
    content = await file.read()
    object_name = f"{current_user.id}/{uuid.uuid4()}_{file.filename}"
    put_object(object_name=object_name, content=content, content_type=file.content_type)

    # 2) создаём анализ в БД
    analysis = Analysis(
        user_id=current_user.id,
        source="web",
        format=(file.content_type or "file"),
        status="received",
        document_ref=object_name,
    )
    session.add(analysis)
    await session.commit()
    await session.refresh(analysis)

    # 3) OCR и извлечение показателей (MVP)
    ocr_text: str | None = None
    tests: list[dict] = []
    ctype = (file.content_type or "").lower()
    if ctype.startswith("image/"):
        try:
            ocr_text = ocr_image_bytes(content)
            tests = extract_tests_from_text(ocr_text)
        except Exception:
            ocr_text = None
            tests = []
    elif ctype in ("application/pdf",) or ctype.endswith("+pdf"):
        try:
            # 1) Пробуем структурно извлечь из "цифрового" PDF по координатам
            tests, preview = extract_tests_from_pdf(content)
            ocr_text = preview or None
            # 2) Если не получилось — делаем OCR и построчный парсинг
            if not tests:
                ocr_text = ocr_pdf_bytes(content)
                tests = extract_tests_from_text(ocr_text)
        except Exception:
            ocr_text = None
            tests = []

    # Важно: если OCR/парсер ничего не нашёл, оставляем пусто (это честнее, чем одинаковая заглушка).
    # Заглушку оставим только как ручной fallback через env.
    if not tests and (str(__import__("os").environ.get("USE_MOCK_TESTS", "false")).lower() == "true"):
        tests = mock_extract_tests(ocr_text or "")

    analysis.ocr_text = ocr_text
    for t in tests:
        value = Decimal(str(t.get("value"))) if t.get("value") is not None else None
        ref_min = Decimal(str(t.get("ref_min"))) if t.get("ref_min") is not None else None
        ref_max = Decimal(str(t.get("ref_max"))) if t.get("ref_max") is not None else None

        ind = TestIndicator(
            analysis_id=analysis.id,
            test_name=str(t.get("test_name")),
            value=value,
            units=t.get("units"),
            ref_min=ref_min,
            ref_max=ref_max,
            deviation=compute_deviation(value=value, ref_min=ref_min, ref_max=ref_max),
            comment=None,
        )
        session.add(ind)

    analysis.status = "processed"
    await session.commit()

    return UploadResponse(analysis_id=analysis.id, status=analysis.status)


@router.get("/history")
async def history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # упрощённо: список анализов пользователя
    from sqlalchemy import select

    rows = (await session.execute(select(Analysis).where(Analysis.user_id == current_user.id))).scalars().all()
    return [
        {
            "id": a.id,
            "date": a.date.isoformat(),
            "status": a.status,
            "source": a.source,
            "format": a.format,
        }
        for a in rows
    ]

