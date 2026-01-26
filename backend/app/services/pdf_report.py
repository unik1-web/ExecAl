from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def build_report_pdf(
    *,
    analysis_id: int,
    indicators: list[dict],
    deviations: list[dict],
    recommendations: list[dict],
) -> bytes:
    """
    MVP: простой PDF без таблиц/стилей, чтобы экспорт работал сразу.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # Шрифт: базовый Helvetica; при необходимости можно добавить TTF позже.
    y = height - 20 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, f"MedicalLab Report (analysis_id={analysis_id})")
    y -= 12 * mm

    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, y, "Индикаторы:")
    y -= 8 * mm

    for ind in indicators:
        line = (
            f"- {ind.get('test_name')}: {ind.get('value')} {ind.get('units') or ''} "
            f"(ref {ind.get('ref_min')}..{ind.get('ref_max')}) dev={ind.get('deviation')}"
        )
        y = _draw_wrapped(c, 20 * mm, y, line, max_width=width - 40 * mm)
        y -= 2 * mm
        if y < 25 * mm:
            c.showPage()
            y = height - 20 * mm
            c.setFont("Helvetica", 11)

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Отклонения:")
    y -= 8 * mm
    c.setFont("Helvetica", 11)
    if not deviations:
        c.drawString(20 * mm, y, "- Нет")
        y -= 6 * mm
    else:
        for d in deviations:
            line = f"- {d.get('test')}: {d.get('deviation')} (value={d.get('value')} {d.get('units') or ''})"
            y = _draw_wrapped(c, 20 * mm, y, line, max_width=width - 40 * mm)
            y -= 2 * mm
            if y < 25 * mm:
                c.showPage()
                y = height - 20 * mm
                c.setFont("Helvetica", 11)

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Рекомендации:")
    y -= 8 * mm
    c.setFont("Helvetica", 11)
    for r in recommendations or [{"text": "Нет"}]:
        line = f"- {r.get('text')}"
        y = _draw_wrapped(c, 20 * mm, y, line, max_width=width - 40 * mm)
        y -= 2 * mm
        if y < 25 * mm:
            c.showPage()
            y = height - 20 * mm
            c.setFont("Helvetica", 11)

    c.showPage()
    c.save()
    return buf.getvalue()


def _draw_wrapped(c: canvas.Canvas, x: float, y: float, text: str, *, max_width: float) -> float:
    """
    Простейший перенос по ширине для Helvetica.
    """
    words = str(text).split()
    line = ""
    for w in words:
        candidate = (line + " " + w).strip()
        if c.stringWidth(candidate, "Helvetica", 11) <= max_width:
            line = candidate
        else:
            c.drawString(x, y, line)
            y -= 5 * mm
            line = w
    if line:
        c.drawString(x, y, line)
        y -= 5 * mm
    return y

