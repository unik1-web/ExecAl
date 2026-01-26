import os
import io
import re

import pytesseract
from PIL import Image


def ocr_image_bytes(image_bytes: bytes, lang: str = "rus+eng") -> str:
    """
    OCR для PNG/JPG. Для PDF на MVP-этапе лучше сначала конвертировать в изображения.
    """
    tcmd = os.environ.get("TESSERACT_CMD")
    if tcmd:
        pytesseract.pytesseract.tesseract_cmd = tcmd

    img = Image.open(io.BytesIO(image_bytes))  # type: ignore[name-defined]
    return pytesseract.image_to_string(img, lang=lang)


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

