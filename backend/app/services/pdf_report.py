from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_report_pdf(
    *,
    analysis_id: int,
    indicators: list[dict],
    deviations: list[dict],
    recommendations: list[dict],
) -> bytes:
    """
    "Нормальный" PDF для MVP: кириллица (DejaVu), таблица показателей, блоки отклонений/рекомендаций.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Отчёт анализа #{analysis_id}",
        author="ExecAl",
    )

    font_name, font_bold = _register_fonts()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "ExecAlNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10.5,
        leading=13,
    )
    title = ParagraphStyle(
        "ExecAlTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=16,
        leading=20,
        spaceAfter=6 * mm,
    )
    h2 = ParagraphStyle(
        "ExecAlH2",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=12.5,
        leading=16,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    )

    story: list = []
    story.append(Paragraph(f"Отчёт по анализу № {analysis_id}", title))
    story.append(Paragraph("Сформировано автоматически (MVP).", normal))

    # Таблица показателей
    story.append(Paragraph("Показатели", h2))
    if not indicators:
        story.append(
            Paragraph(
                "Не удалось автоматически извлечь показатели из документа. "
                "Проверьте качество скана/контраст или предоставьте более читаемый файл.",
                normal,
            )
        )
        story.append(Spacer(1, 3 * mm))
    table_data: list[list] = [
        [
            Paragraph("<b>Показатель</b>", normal),
            Paragraph("<b>Значение</b>", normal),
            Paragraph("<b>Ед.</b>", normal),
            Paragraph("<b>Реф.</b>", normal),
            Paragraph("<b>Откл.</b>", normal),
        ]
    ]

    def fmt(v):
        return "" if v is None else str(v)

    for ind in indicators:
        ref = ""
        if ind.get("ref_min") is not None or ind.get("ref_max") is not None:
            ref = f"{fmt(ind.get('ref_min'))} – {fmt(ind.get('ref_max'))}"
        dev = fmt(ind.get("deviation"))
        table_data.append(
            [
                Paragraph(str(ind.get("test_name") or ""), normal),
                Paragraph(fmt(ind.get("value")), normal),
                Paragraph(fmt(ind.get("units")), normal),
                Paragraph(ref, normal),
                Paragraph(dev, normal),
            ]
        )

    table = Table(
        table_data,
        colWidths=[62 * mm, 25 * mm, 18 * mm, 32 * mm, 18 * mm],
        hAlign="LEFT",
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cfcfcf")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    # Отклонения
    story.append(Paragraph("Отклонения", h2))
    if not deviations:
        story.append(Paragraph("Отклонений не выявлено.", normal))
    else:
        for d in deviations:
            test = d.get("test") or d.get("test_name") or "Показатель"
            dev = d.get("deviation") or ""
            reason = d.get("reason") or ""
            story.append(Paragraph(f"• <b>{test}</b>: {dev}. {reason}", normal))

    # Рекомендации
    story.append(Paragraph("Рекомендации", h2))
    if not recommendations:
        story.append(Paragraph("Рекомендаций нет.", normal))
    else:
        for r in recommendations:
            text = r.get("text") or ""
            story.append(Paragraph(f"• {text}", normal))

    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "Важно: отчёт носит информационный характер и не заменяет консультацию врача.",
            ParagraphStyle("ExecAlNote", parent=normal, textColor=colors.HexColor("#555555")),
        )
    )

    doc.build(story)
    return buf.getvalue()


def _register_fonts() -> tuple[str, str]:
    """
    Регистрируем DejaVuSans (кириллица) если шрифты доступны в системе.
    В Debian-slim шрифты ставим через apt: fonts-dejavu-core.
    """
    # уже зарегистрированы
    if "DejaVuSans" in pdfmetrics.getRegisteredFontNames():
        return "DejaVuSans", "DejaVuSans-Bold"

    env_font = os.environ.get("REPORT_FONT_PATH", "").strip()
    env_font_bold = os.environ.get("REPORT_FONT_BOLD_PATH", "").strip()

    candidates = [
        Path(env_font) if env_font else None,
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    candidates_bold = [
        Path(env_font_bold) if env_font_bold else None,
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]

    font = next((p for p in candidates if p is not None and p.exists()), None)
    font_bold = next((p for p in candidates_bold if p is not None and p.exists()), None)

    if font and font_bold:
        pdfmetrics.registerFont(TTFont("DejaVuSans", str(font)))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(font_bold)))
        return "DejaVuSans", "DejaVuSans-Bold"

    # fallback (без кириллицы, но хоть что-то)
    return "Helvetica", "Helvetica-Bold"

