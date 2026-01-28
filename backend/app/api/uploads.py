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


def _merge_tests(primary: list[dict], secondary: list[dict]) -> list[dict]:
    """
    Сливаем результаты двух парсеров (структурный PDF + OCR-текст) с дедупом по имени.
    Предпочитаем запись, где есть числовое value/референсы/единицы/комментарий.
    """

    def _key(t: dict) -> str:
        return " ".join(str(t.get("test_name", "")).lower().split())

    def _score(t: dict) -> int:
        s = 0
        if t.get("value") is not None:
            s += 3
        if t.get("units"):
            s += 1
        if t.get("ref_min") is not None or t.get("ref_max") is not None:
            s += 1
        if t.get("comment"):
            s += 1
        return s

    out: dict[str, dict] = {}
    for t in primary + secondary:
        k = _key(t)
        if not k:
            continue
        if k not in out or _score(t) > _score(out[k]):
            out[k] = t
    return list(out.values())


def _truncate_text(s: str | None, limit: int = 15000) -> str | None:
    if not s:
        return None
    s = s.strip()
    if len(s) <= limit:
        return s
    return s[:limit] + "\n\n...[truncated]..."


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
            import os

            pdf_max_pages = int(os.environ.get("PDF_MAX_PAGES", "4"))
            min_pdf_tests = int(os.environ.get("PDF_MIN_TESTS", "3"))

            # 1) Пробуем структурно извлечь из "цифрового" PDF по координатам
            tests_struct, preview = extract_tests_from_pdf(content, max_pages=pdf_max_pages)
            ocr_text = _truncate_text(preview) or None

            # 2) Fallback: если получилось слишком мало показателей — делаем OCR и построчный парсинг
            tests = tests_struct
            if len(tests_struct) < min_pdf_tests:
                ocr_full = ocr_pdf_bytes(content, max_pages=pdf_max_pages)
                tests_ocr = extract_tests_from_text(ocr_full)
                tests = _merge_tests(tests_ocr, tests_struct) if len(tests_ocr) > len(tests_struct) else _merge_tests(tests_struct, tests_ocr)
                # для пользователя/отладки полезнее хранить именно OCR-текст, а не preview из PDF
                ocr_text = _truncate_text(ocr_full) or ocr_text
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
            comment=t.get("comment"),
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

