import os
import io
import re

import pytesseract
from PIL import Image
import fitz  # PyMuPDF


def ocr_image_bytes(image_bytes: bytes, lang: str = "rus+eng") -> str:
    """
    OCR для PNG/JPG. Для PDF на MVP-этапе лучше сначала конвертировать в изображения.
    """
    tcmd = os.environ.get("TESSERACT_CMD")
    if tcmd:
        pytesseract.pytesseract.tesseract_cmd = tcmd

    img = Image.open(io.BytesIO(image_bytes))  # type: ignore[name-defined]
    return pytesseract.image_to_string(img, lang=lang)


def ocr_pdf_bytes(pdf_bytes: bytes, lang: str = "rus+eng", max_pages: int = 2) -> str:
    """
    PDF -> text:
    - сначала пробуем извлечь текст напрямую (для "цифровых" PDF это лучше и быстрее)
    - если текста нет/мало, делаем OCR: рендерим первые max_pages страниц в изображения и прогоняем Tesseract.
    """
    tcmd = os.environ.get("TESSERACT_CMD")
    if tcmd:
        pytesseract.pytesseract.tesseract_cmd = tcmd

    text_parts: list[str] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        pages = min(len(doc), max_pages)
        for i in range(pages):
            page = doc.load_page(i)
            direct = (page.get_text("text") or "").strip()
            if len(direct) >= 40:
                text_parts.append(direct)
                continue

            # OCR fallback: 2x масштаб даёт заметно лучше OCR
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            text_parts.append(pytesseract.image_to_string(img, lang=lang))
    return "\n\n".join([t for t in text_parts if t])


def extract_tests_from_text(text: str) -> list[dict]:
    """
    MVP-парсер: пытается вытащить несколько показателей из OCR-текста.
    Если не получилось — вернём пустой список, чтобы вызывающий код мог сделать fallback.
    """
    norm = " ".join(text.replace("\n", " ").split())
    if not norm:
        return []

    def _num(x: str) -> float:
        return float(x.replace(",", "."))

    tests: list[dict] = []

    # Glucose / Глюкоза
    m = re.search(r"(glucose|глюкоз[аы])\s*[:\-]?\s*([0-9]+[.,]?[0-9]*)", norm, re.IGNORECASE)
    if m:
        tests.append(
            {
                "test_name": "Glucose",
                "value": _num(m.group(2)),
                "units": "mmol/L",
                "ref_min": 3.9,
                "ref_max": 5.5,
            }
        )

    # Cholesterol / Холестерин
    m = re.search(
        r"(cholesterol|холестерин)\s*[:\-]?\s*([0-9]+[.,]?[0-9]*)", norm, re.IGNORECASE
    )
    if m:
        tests.append(
            {
                "test_name": "Cholesterol",
                "value": _num(m.group(2)),
                "units": "mg/dL",
                "ref_min": 0,
                "ref_max": 200,
            }
        )

    # Общий парсер строк вида:
    # "Глюкоза 5.6 ммоль/л 3.9-5.5" или "ALT 42 U/L (0-40)" и т.п.
    # Важно: это эвристика, но она даёт разные результаты на разных документах.
    row_re = re.compile(
        r"(?P<name>[A-Za-zА-Яа-я][A-Za-zА-Яа-я0-9/\-\s]{2,50}?)\s+"
        r"(?P<value>[0-9]+[.,]?[0-9]*)\s*"
        r"(?P<units>[A-Za-zА-Яа-я/%µμ\.]{0,12})\s*"
        r"(?:\(?\s*(?P<refmin>[0-9]+[.,]?[0-9]*)\s*[-–]\s*(?P<refmax>[0-9]+[.,]?[0-9]*)\s*\)?)?",
        re.IGNORECASE,
    )
    for m2 in row_re.finditer(norm):
        name = " ".join(m2.group("name").split()).strip(" .,:;()[]")
        if not name or len(name) < 3:
            continue
        value = _num(m2.group("value"))
        units = (m2.group("units") or "").strip()
        refmin = m2.group("refmin")
        refmax = m2.group("refmax")
        t = {
            "test_name": name[:255],
            "value": value,
            "units": units or None,
            "ref_min": _num(refmin) if refmin else None,
            "ref_max": _num(refmax) if refmax else None,
        }
        # не плодим дубликаты по имени
        if not any(x.get("test_name", "").lower() == t["test_name"].lower() for x in tests):
            tests.append(t)

    return tests


def mock_extract_tests(_: str):
    # Заглушка из документа: минимальный набор показателей.
    return [
        {
            "test_name": "Glucose",
            "value": 5.6,
            "units": "mmol/L",
            "ref_min": 3.9,
            "ref_max": 5.5,
        },
        {
            "test_name": "Cholesterol",
            "value": 190,
            "units": "mg/dL",
            "ref_min": 0,
            "ref_max": 200,
        },
    ]

