from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Analysis, TestIndicator, User
from ..services.pdf_report import build_report_pdf
from ..services.report_generator import generate_recommendations
from .deps import get_current_user

router = APIRouter()


@router.get("/{analysis_id}")
async def get_report(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    analysis = await session.scalar(
        select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    indicators = (
        (await session.execute(select(TestIndicator).where(TestIndicator.analysis_id == analysis.id)))
        .scalars()
        .all()
    )

    deviations = [
        {
            "test": i.test_name,
            "value": float(i.value) if i.value is not None else None,
            "units": i.units,
            "deviation": i.deviation,
            "reason": "MVP: причина уточняется врачом",
        }
        for i in indicators
        if i.deviation in ("low", "high")
    ]

    recs = generate_recommendations(deviations)

    report = {
        "analysis_id": analysis.id,
        "ocr_text": analysis.ocr_text,
        "deviations": deviations,
        "recommendations": [{"text": r.text, "doctor_contact": r.doctor_contact} for r in recs],
        "indicators": [
            {
                "test_name": i.test_name,
                "value": float(i.value) if i.value is not None else None,
                "units": i.units,
                "ref_min": float(i.ref_min) if i.ref_min is not None else None,
                "ref_max": float(i.ref_max) if i.ref_max is not None else None,
                "deviation": i.deviation,
                "comment": i.comment,
            }
            for i in indicators
        ],
    }
    return report


@router.get("/{analysis_id}/pdf")
async def get_report_pdf(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    analysis = await session.scalar(
        select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    indicators_rows = (
        (await session.execute(select(TestIndicator).where(TestIndicator.analysis_id == analysis.id)))
        .scalars()
        .all()
    )

    indicators = [
        {
            "test_name": i.test_name,
            "value": float(i.value) if i.value is not None else None,
            "units": i.units,
            "ref_min": float(i.ref_min) if i.ref_min is not None else None,
            "ref_max": float(i.ref_max) if i.ref_max is not None else None,
            "deviation": i.deviation,
        }
        for i in indicators_rows
    ]

    deviations = [
        {
            "test": i.test_name,
            "value": float(i.value) if i.value is not None else None,
            "units": i.units,
            "deviation": i.deviation,
            "reason": "MVP: причина уточняется врачом",
        }
        for i in indicators_rows
        if i.deviation in ("low", "high")
    ]

    recs = generate_recommendations(deviations)
    recommendations = [{"text": r.text, "doctor_contact": r.doctor_contact} for r in recs]

    pdf_bytes = build_report_pdf(
        analysis_id=analysis.id,
        indicators=indicators,
        deviations=deviations,
        recommendations=recommendations,
    )

    filename = f"report_{analysis.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

