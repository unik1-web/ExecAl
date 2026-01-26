import os

import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добро пожаловать в MedicalLab. Отправьте документ (MVP skeleton).")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return
    await update.message.reply_text("Документ получен. MVP skeleton: загрузка в API пока не подключена.")


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

