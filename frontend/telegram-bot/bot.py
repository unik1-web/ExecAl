import os
from io import BytesIO

import httpx
from telegram import InputFile, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
BOT_EMAIL = os.environ.get("BOT_EMAIL", "bot@example.com")
BOT_PASSWORD = os.environ.get("BOT_PASSWORD", "botpassword123")

_cached_access_token: str | None = None


async def _ensure_access_token() -> str:
    """
    Сервисная авторизация: бот регистрируется (если нужно) и логинится в backend,
    чтобы иметь JWT для /upload/document и /report/*.
    """
    global _cached_access_token
    if _cached_access_token:
        return _cached_access_token

    async with httpx.AsyncClient(timeout=20) as client:
        # регистрация может вернуть 400 если пользователь уже существует — это ок
        try:
            await client.post(
                f"{BACKEND_BASE_URL}/auth/register",
                json={"email": BOT_EMAIL, "password": BOT_PASSWORD},
            )
        except Exception:
            # не блокируемся на сетевых мелочах при register
            pass

        r = await client.post(
            f"{BACKEND_BASE_URL}/auth/login",
            json={"email": BOT_EMAIL, "password": BOT_PASSWORD},
        )
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token") or ""
        if not token:
            raise RuntimeError(f"Не удалось получить access_token от backend: {data}")
        _cached_access_token = token
        return token


async def _upload_to_backend(*, filename: str, content_type: str | None, content: bytes) -> int:
    token = await _ensure_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, content, content_type or "application/octet-stream")}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{BACKEND_BASE_URL}/upload/document", headers=headers, files=files)
        r.raise_for_status()
        data = r.json()
        analysis_id = data.get("analysis_id") or data.get("analysisId")
        if not analysis_id:
            raise RuntimeError(f"Backend не вернул analysis_id: {data}")
        return int(analysis_id)


async def _fetch_report(analysis_id: int) -> dict:
    token = await _ensure_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"{BACKEND_BASE_URL}/report/{analysis_id}", headers=headers)
        r.raise_for_status()
        return r.json()


async def _fetch_report_pdf(analysis_id: int) -> bytes:
    token = await _ensure_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(f"{BACKEND_BASE_URL}/report/{analysis_id}/pdf", headers=headers)
        r.raise_for_status()
        return bytes(r.content)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать в MedicalLab.\n"
        "Отправьте PDF/PNG/JPG — я загружу документ в API, сделаю анализ и пришлю отчёт + PDF."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return
    msg = update.message
    await msg.reply_text("Документ получен. Загружаю в API и формирую отчёт...")

    try:
        tg_file = await doc.get_file()
        content = await tg_file.download_as_bytearray()
        analysis_id = await _upload_to_backend(
            filename=doc.file_name or "document",
            content_type=getattr(doc, "mime_type", None),
            content=bytes(content),
        )

        report = await _fetch_report(analysis_id)
        indicators = report.get("indicators") or []

        # короткая сводка
        lines: list[str] = [f"Готово. analysis_id={analysis_id}"]
        if indicators:
            lines.append("Показатели:")
            for ind in indicators[:12]:
                name = ind.get("test_name") or "Показатель"
                val = ind.get("value")
                units = ind.get("units") or ""
                rmin = ind.get("ref_min")
                rmax = ind.get("ref_max")
                comment = ind.get("comment")
                if val is None and comment:
                    lines.append(f"- {name}: {comment}")
                else:
                    ref = ""
                    if rmin is None and rmax is not None:
                        ref = f" (реф: < {rmax})"
                    elif rmin is not None and rmax is None:
                        ref = f" (реф: > {rmin})"
                    elif rmin is not None or rmax is not None:
                        ref = f" (реф: {rmin} – {rmax})"
                    lines.append(f"- {name}: {val} {units}{ref}".strip())
            if len(indicators) > 12:
                lines.append(f"... и ещё {len(indicators) - 12}")
        else:
            lines.append("Не удалось автоматически извлечь показатели из документа.")

        await msg.reply_text("\n".join(lines))

        # PDF отчёт
        pdf_bytes = await _fetch_report_pdf(analysis_id)
        bio = BytesIO(pdf_bytes)
        bio.name = f"report_{analysis_id}.pdf"
        await msg.reply_document(document=InputFile(bio), filename=bio.name)
    except Exception as e:
        await msg.reply_text(f"Ошибка обработки документа: {e}")


async def ping_backend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{BACKEND_BASE_URL}/")
        await update.message.reply_text(f"Backend: {r.status_code} {r.text}")
    except Exception as e:
        await update.message.reply_text(f"Backend недоступен: {e}")


def main():
    if not TOKEN or TOKEN == "CHANGE_ME":
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN не задан. Запускайте контейнер с профилем telegram и реальным токеном."
        )

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping_backend))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.run_polling()


if __name__ == "__main__":
    main()

