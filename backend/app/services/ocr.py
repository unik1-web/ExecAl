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

    img = Image.open(io.BytesIO(image_bytes))
    # лёгкая предобработка для сканов/скриншотов
    img = img.convert("RGB")
    w, h = img.size
    if max(w, h) < 1200:
        img = img.resize((w * 2, h * 2))
    gray = img.convert("L")
    bw = gray.point(lambda p: 255 if p > 170 else 0)
    # PSM 6 обычно лучше для "табличных" скриншотов
    config = "--oem 1 --psm 6"
    return pytesseract.image_to_string(bw, lang=lang, config=config)


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

        # Служебные/паспортные строки, которые не должны становиться "показателями"
        blacklist = (
            "страница",
            "дата",
            "пол пациента",
            "согласие",
            "обработк",
            "персональн",
            "пдн",
            "паспорт",
            "телефон",
            "адрес",
            "заказа",
            "номер заказа",
            "фамилия",
            "имя пациента",
            "отчество",
            "гост",
            "iso",
            "направляющий",
            "диагноз",
        )

        def _first_number(s: str) -> float | None:
            m = re.search(r"([0-9]+(?:[.,][0-9]+)?)", s)
            if not m:
                return None
            return _num(m.group(1))

        def _is_noise_name(name: str) -> bool:
            n = name.lower()
            if any(b in n for b in blacklist):
                return True
            # много цифр/служебных символов -> скорее номер/ГОСТ/код
            digits = sum(ch.isdigit() for ch in name)
            if digits / max(1, len(name)) > 0.25:
                return True
            if "№" in name or " N" in name:
                return True
            return False

        # Ищем заголовок таблицы более устойчиво: по отдельным словам и кластеризации по Y.
        # Это работает даже если "Ед. изм." / "Нормальные значения" разбиты на несколько спанов/блоков.
        merged_rows = [_merge_row(r) for r in rows]

        header_idx: int | None = None
        header_y: float | None = None
        col_value_x: float | None = None
        col_units_x: float | None = None
        col_ref_x: float | None = None
        col_name_end_x: float | None = None

        kw_map = {
            "name": ("исслед", "показат"),
            "value": ("значен",),
            "units": ("ед", "ед.", "ед изм", "ед.изм"),
            "ref": ("норм", "реф"),
        }

        matches: list[tuple[str, float, float, float]] = []  # (kind, xcenter, ycenter, x1)
        for row in merged_rows:
            for x in row:
                t = x["text"].lower()
                yc = (x["y0"] + x["y1"]) / 2.0
                xc = (x["x0"] + x["x1"]) / 2.0
                for kind, kws in kw_map.items():
                    if any(k in t for k in kws):
                        matches.append((kind, xc, yc, x["x1"]))
                        break

        # кластеризация по Y
        if matches:
            matches.sort(key=lambda m: m[2])
            bands: list[dict] = []
            band_tol = 4.5
            for kind, xc, yc, x1 in matches:
                if not bands:
                    bands.append({"y": yc, "kinds": {kind}, "points": [(kind, xc, x1)]})
                    continue
                if abs(yc - bands[-1]["y"]) <= band_tol:
                    b = bands[-1]
                    b["kinds"].add(kind)
                    b["points"].append((kind, xc, x1))
                    # обновляем среднее Y
                    b["y"] = (b["y"] * (len(b["points"]) - 1) + yc) / len(b["points"])
                else:
                    bands.append({"y": yc, "kinds": {kind}, "points": [(kind, xc, x1)]})

            best = max(bands, key=lambda b: (len(b["kinds"]), len(b["points"])))
            if len(best["kinds"]) >= 3:
                header_y = float(best["y"])
                # берём x по каждому типу в этом бэнде
                def _median(xs: list[float]) -> float:
                    xs = sorted(xs)
                    return xs[len(xs) // 2]

                xs_value = [xc for (k, xc, _x1) in best["points"] if k == "value"]
                xs_units = [xc for (k, xc, _x1) in best["points"] if k == "units"]
                xs_ref = [xc for (k, xc, _x1) in best["points"] if k == "ref"]
                xs_name_end = [_x1 for (k, _xc, _x1) in best["points"] if k == "name"]

                if xs_value:
                    col_value_x = _median(xs_value)
                if xs_units:
                    col_units_x = _median(xs_units)
                if xs_ref:
                    col_ref_x = _median(xs_ref)
                if xs_name_end:
                    col_name_end_x = max(xs_name_end)

                # найдём индекс строки, ближайшей к header_y
                header_idx = min(
                    range(len(merged_rows)),
                    key=lambda i: abs(
                        (sum((x["y0"] + x["y1"]) / 2.0 for x in merged_rows[i]) / max(1, len(merged_rows[i])))
                        - header_y
                    ),
                )

        # Fallback: если заголовок не нашли, используем старую эвристику по x-распределению чисел
        value_c = None
        ref_c = None
        if header_idx is None:
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
        else:
            # границы колонок из заголовка (самый надёжный вариант для PDF-таблиц)
            if col_value_x is None or col_units_x is None or col_ref_x is None:
                # если не смогли вытащить позиции колонок из заголовка — fallback
                header_idx = None
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

        tests: list[dict] = []
        for idx, row in enumerate(merged_rows):
            # если нашли таблицу — обрабатываем только строки ниже заголовка таблицы
            if header_idx is not None:
                if idx <= header_idx:
                    continue

            texts = " ".join(x["text"] for x in row).lower()
            if any(b in texts for b in blacklist):
                continue

            # Если у нас есть координаты колонок (header найден) — раскладываем по колонкам
            if header_idx is not None and col_value_x is not None and col_units_x is not None and col_ref_x is not None:
                name_end = (col_name_end_x or (col_value_x - 10))
                sep_name_value = (name_end + col_value_x) / 2.0
                sep_value_units = (col_value_x + col_units_x) / 2.0
                sep_units_ref = (col_units_x + col_ref_x) / 2.0

                name_tokens: list[str] = []
                value_tokens: list[str] = []
                units_tokens: list[str] = []
                ref_tokens: list[str] = []

                for x in sorted(row, key=lambda t: t["x0"]):
                    xc = (x["x0"] + x["x1"]) / 2.0
                    tx = x["text"]
                    if xc < sep_name_value:
                        name_tokens.append(tx)
                    elif xc < sep_value_units:
                        value_tokens.append(tx)
                    elif xc < sep_units_ref:
                        units_tokens.append(tx)
                    else:
                        ref_tokens.append(tx)

                name = " ".join(name_tokens).strip(" .,:;()[]")
                if not name or len(name) < 3 or len(name) > 80:
                    continue
                if not re.match(r"^[A-Za-zА-Яа-я]", name):
                    continue
                # отсечём явно “мусорные” имена
                if _is_noise_name(name):
                    continue

                value = None
                for vt in value_tokens:
                    if _NUM_RE.match(vt) or re.search(r"[0-9]", vt):
                        value = _first_number(vt)
                        if value is not None:
                            break
                if value is None:
                    continue

                units = None
                u = " ".join(units_tokens).strip()
                if u and len(u) <= 20 and _UNITS_RE.search(u):
                    units = u

                ref_min = None
                ref_max = None
                ref_joined = " ".join(ref_tokens).replace("—", "-").replace("–", "-")
                m = _RANGE_RE.search(ref_joined)
                if m:
                    ref_min = _num(m.group("min"))
                    ref_max = _num(m.group("max"))
                else:
                    nums = [ _first_number(t) for t in ref_tokens ]
                    nums = [n for n in nums if n is not None]
                    if len(nums) >= 2:
                        ref_min, ref_max = nums[0], nums[1]

                tests.append(
                    {
                        "test_name": name[:255],
                        "value": value,
                        "units": units,
                        "ref_min": ref_min,
                        "ref_max": ref_max,
                    }
                )
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
            if _is_noise_name(name):
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
        r"(?P<units>[A-Za-zА-Яа-я/%µμ\./×х\^]{0,12})\s*"
        r"(?:\(?\s*(?P<refmin>[0-9]+[.,]?[0-9]*)\s*[-–]\s*(?P<refmax>[0-9]+[.,]?[0-9]*)\s*\)?)?",
        re.IGNORECASE,
    )

    ref_op_re = re.compile(r"(?P<op><=|>=|<|>)\s*(?P<num>[0-9]+[.,]?[0-9]*)")

    skip_keywords = (
        "инвитро",
        "пол",
        "возраст",
        "адрес",
        "дата",
        "врач",
        "пациент",
        "инз",
        "номер заказа",
        "заказ",
        "исполнитель",
        "подпись",
        "технология",
        "оборудование",
        "внимание",
        "результаты исследований",
        "не являются диагнозом",
        "необходима консультация",
        "www.",
        "http",
    )

    def is_table_header(line: str) -> bool:
        l = line.lower()
        has_test = ("исслед" in l) or ("показат" in l)
        has_value = ("результ" in l) or ("значен" in l)
        has_units = ("ед" in l) or ("единиц" in l) or ("ед. изм" in l) or ("ед изм" in l)
        has_ref = ("рефер" in l) or ("норм" in l) or ("нормальн" in l)
        return has_test and has_value and has_units and has_ref

    lines = [ln.strip() for ln in text.splitlines()]
    start_idx = 0
    for i, ln in enumerate(lines):
        if is_table_header(ln):
            start_idx = i + 1
            break

    # Построчно — меньше "смешивания" колонок
    for line in (ln.strip() for ln in lines[start_idx:]):
        if not line:
            continue
        low = line.lower()
        if any(k in low for k in skip_keywords):
            # если это предупреждение/футер — можно прекратить парсинг
            if "внимание" in low:
                break
            continue
        # защита от "паспортных" строк: слишком много цифр и двоеточие/точки
        digits = sum(ch.isdigit() for ch in line)
        if digits / max(1, len(line)) > 0.35 and (":" in line or "." in line):
            continue

        for m2 in row_re.finditer(line):
            name = " ".join(m2.group("name").split()).strip(" .,:;()[]")
            if not name or len(name) < 3:
                continue
            if any(k in name.lower() for k in skip_keywords):
                continue
            value = _num(m2.group("value"))
            units = (m2.group("units") or "").strip()
            refmin = m2.group("refmin")
            refmax = m2.group("refmax")

            ref_min = _num(refmin) if refmin else None
            ref_max = _num(refmax) if refmax else None
            # поддержка референсов вида "<7,29" / "> 1.2"
            if ref_min is None and ref_max is None:
                mref = ref_op_re.search(line)
                if mref:
                    op = mref.group("op")
                    num = _num(mref.group("num"))
                    if op in ("<", "<="):
                        ref_max = num
                    else:
                        ref_min = num

            t = {
                "test_name": name[:255],
                "value": value,
                "units": units or None,
                "ref_min": ref_min,
                "ref_max": ref_max,
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

