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


_NUM_RE = re.compile(r"^[0-9]+([.,][0-9]+)?$")
_RANGE_RE = re.compile(r"(?P<min>[0-9]+(?:[.,][0-9]+)?)\s*[-–]\s*(?P<max>[0-9]+(?:[.,][0-9]+)?)")
_UNITS_RE = re.compile(r"[A-Za-zА-Яа-я/%µμ\^]|/|×|х")


def extract_tests_from_pdf(pdf_bytes: bytes, max_pages: int = 2) -> tuple[list[dict], str]:
    """
    Структурное извлечение из PDF по координатам (для "цифровых" PDF таблиц).
    Возвращает (tests, extracted_text_preview).
    """
    def _num(x: str) -> float:
        return float(x.replace(",", "."))

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        pages = min(len(doc), max_pages)
        tokens: list[dict] = []
        text_preview_parts: list[str] = []

        for i in range(pages):
            page = doc.load_page(i)
            text_preview_parts.append((page.get_text("text") or "").strip())
            d = page.get_text("dict")
            for b in d.get("blocks", []):
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        t = (span.get("text") or "").strip()
                        if not t:
                            continue
                        x0, y0, x1, y1 = span.get("bbox", (0, 0, 0, 0))
                        tokens.append({"text": t, "x0": float(x0), "x1": float(x1), "y0": float(y0), "y1": float(y1)})

        preview = "\n\n".join([p for p in text_preview_parts if p])

        if not tokens:
            return [], preview

        # 1D k-means (k=2) по x0 для "чисто числовых" токенов — разделяем колонку значений и колонку референсов
        num_x = [t["x0"] for t in tokens if _NUM_RE.match(t["text"])]
        if len(num_x) < 6:
            return [], preview

        xs = sorted(num_x)
        c1 = xs[int(len(xs) * 0.25)]
        c2 = xs[int(len(xs) * 0.75)]
        for _ in range(10):
            g1 = [x for x in xs if abs(x - c1) <= abs(x - c2)]
            g2 = [x for x in xs if abs(x - c2) < abs(x - c1)]
            if g1:
                c1 = sum(g1) / len(g1)
            if g2:
                c2 = sum(g2) / len(g2)
        value_c, ref_c = (c1, c2) if c1 < c2 else (c2, c1)

        # группируем по строкам (y)
        tokens.sort(key=lambda t: ((t["y0"] + t["y1"]) / 2.0, t["x0"]))
        rows: list[list[dict]] = []
        tol = 2.8  # px
        for t in tokens:
            y = (t["y0"] + t["y1"]) / 2.0
            if not rows:
                rows.append([t])
                continue
            last = rows[-1]
            y_last = sum((x["y0"] + x["y1"]) / 2.0 for x in last) / len(last)
            if abs(y - y_last) <= tol:
                last.append(t)
            else:
                rows.append([t])

        def _merge_row(row: list[dict]) -> list[dict]:
            row = sorted(row, key=lambda t: t["x0"])
            merged: list[dict] = []
            for t in row:
                if not merged:
                    merged.append(t.copy())
                    continue
                prev = merged[-1]
                gap = t["x0"] - prev["x1"]
                # если токены близко — считаем одной "ячейкой"
                if gap >= 0 and gap <= 6:
                    prev["text"] = (prev["text"] + " " + t["text"]).strip()
                    prev["x1"] = max(prev["x1"], t["x1"])
                    prev["y0"] = min(prev["y0"], t["y0"])
                    prev["y1"] = max(prev["y1"], t["y1"])
                else:
                    merged.append(t.copy())
            return merged

        blacklist = ("страница", "дата", "пол пациента", "согласие", "паспорт", "телефон", "адрес")

        tests: list[dict] = []
        for row in rows:
            row = _merge_row(row)
            texts = " ".join(x["text"] for x in row).lower()
            if any(b in texts for b in blacklist):
                continue

            # кандидаты значений
            numeric = [(idx, x) for idx, x in enumerate(row) if _NUM_RE.match(x["text"])]
            if not numeric:
                continue

            # value token: ближе всего к value_c
            v_idx, v_tok = min(numeric, key=lambda p: abs(p[1]["x0"] - value_c))
            # защита: значение должно быть реально в "колонке значений"
            if abs(v_tok["x0"] - value_c) > abs(v_tok["x0"] - ref_c):
                continue

            name_parts = [x["text"] for x in row[:v_idx] if x["text"]]
            name = " ".join(name_parts).strip(" .,:;()[]")
            if not name or len(name) < 3 or len(name) > 80:
                continue
            if not re.match(r"^[A-Za-zА-Яа-я]", name):
                continue

            value = _num(v_tok["text"])

            rest = row[v_idx + 1 :]
            units = None
            for x in rest:
                tx = x["text"]
                if _NUM_RE.match(tx):
                    continue
                if len(tx) <= 20 and _UNITS_RE.search(tx):
                    # units обычно между value и ref
                    if x["x0"] < ref_c - 10:
                        units = tx
                        break

            ref_min = None
            ref_max = None
            # 1) референс как "a - b" в одном токене
            for x in rest:
                m = _RANGE_RE.search(x["text"])
                if m:
                    ref_min = _num(m.group("min"))
                    ref_max = _num(m.group("max"))
                    break
            # 2) референс как два числа в правой колонке
            if ref_min is None:
                right_nums = [(idx, x) for idx, x in enumerate(rest) if _NUM_RE.match(x["text"]) and abs(x["x0"] - ref_c) <= 40]
                if len(right_nums) >= 2:
                    ref_min = _num(right_nums[0][1]["text"])
                    ref_max = _num(right_nums[1][1]["text"])

            tests.append(
                {
                    "test_name": name[:255],
                    "value": value,
                    "units": units,
                    "ref_min": ref_min,
                    "ref_max": ref_max,
                }
            )

        return tests, preview


def extract_tests_from_text(text: str) -> list[dict]:
    """
    MVP-парсер: пытается вытащить несколько показателей из OCR-текста.
    Если не получилось — вернём пустой список, чтобы вызывающий код мог сделать fallback.
    """
    if not text or not text.strip():
        return []

    def _num(x: str) -> float:
        return float(x.replace(",", "."))

    tests: list[dict] = []

    # Glucose / Глюкоза
    norm_all = " ".join(text.replace("\n", " ").split())
    m = re.search(r"(glucose|глюкоз[аы])\s*[:\-]?\s*([0-9]+[.,]?[0-9]*)", norm_all, re.IGNORECASE)
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
        r"(cholesterol|холестерин)\s*[:\-]?\s*([0-9]+[.,]?[0-9]*)", norm_all, re.IGNORECASE
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
    # Построчно — меньше "смешивания" колонок
    for line in (ln.strip() for ln in text.splitlines()):
        if not line:
            continue
        for m2 in row_re.finditer(line):
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

