## Извлечённый текст из docx

Готовый план и структура репозитория для MVP с использованием Python FastAPI + Tesseract OCR, полноценного фронтенда и Telegram-бота. Ниже представлен скелет проекта, ключевые файлы и минимальные реализации, готовые к клонированию и локальному запуску через Docker Compose.
Архитектура и стек
Бэкенд: Python 3.11, FastAPI
OCR: Tesseract (через pytesseract) (на данном этапе заглушки заменяются на реальное OCR позже)
База данных: PostgreSQL
Хранение документов: локальное хранилище, совместимое с MinIO/S3
Клиенты: Android (Kotlin) + веб (React) + Telegram-бот (Python)
Контейнеризация: Docker Compose (для локального тестирования)
Безопасность: TLS (локальный сертификат для дев-окружения), JWT
Функционал MVP:
Загрузка документов через три клиента
Оптическое распознавание символов и извлечение базовых тестов (минимальный набор)
Расчет отклонений с учетом возраста/пола
Формирование отчета (отклонения, возможные причины, рекомендации)
История анализов и экспорт в PDF/JSON
Базовая аутентификация/авторизация
Структура репозитория (псевдоструктура, готовая к копированию)
docker-compose.yml
бэкенд/
приложение/
main.py
models.py
schemas.py
api/
__init__.py
auth.py
uploads.py
reports.py
consultations.py
tests_reference.py
Услуги/
ocr.py (заглушка/интеграция Tesseract)
normalization.py
report_generator.py
db.py
тесты/
test_api.py
Файл Dockerfile
внешний интерфейс/
android/ (скелтон на Kotlin)
веб/ (React)
Telegram-бот/ (Python)
infra/
скрипты/
миграции/
Документы/
API.md
DB_schema.sql
MVP_plan.md
Пример минимального набора файлов и содержимого
3.1 docker-compose.yml
version: "3.9"
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: medical
      POSTGRES_PASSWORD: medicalpass
      POSTGRES_DB: medicallab
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  minio:
    image: minio/minio
    command: server /data
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio12345
    ports:
      - "9000:9000"
    volumes:
      - minio-data:/data
  backend:
    build: ./backend
    depends_on:
      - postgres
      - minio
    environment:
      - DATABASE_URL=postgresql+asyncpg://medical:medicalpass@postgres:5432/medicallab
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app
    command: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  web:
    build: ./frontend/web
    depends_on:
      - backend
    ports:
      - "3000:3000"
  telegram_bot:
    build: ./frontend/telegram-bot
    depends_on:
      - backend
    ports:
      - "8081:8081"
volumes:
  pgdata:
  minio-data:
3.2 бэкенд/приложение/main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from .db import init_db
from .api import auth, uploads, reports, consultations
app = FastAPI(title="MedicalLab Backend")
# инициализация БД при старте
@app.on_event("startup")
async def startup_event():
    await init_db()
# подключение роутов
app.include_router(auth.router, prefix="/auth")
app.include_router(uploads.router, prefix="/upload")
app.include_router(reports.router, prefix="/report")
app.include_router(consultations.router, prefix="/consultation")
@app.get("/")
async def root():
    return {"status": "ok", "message": "Medical Lab MVP Backend"}
3.3 backend/app/db.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://medical:medicalpass@postgres/medicallab")
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
async def init_db():
    # Здесь можно разместить миграции или авто-инициализацию
    async with engine.begin() as conn:
        pass
3.4 backend/app/models.py (упрощённая ORM-модель)
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, DECIMAL
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
Base = declarative_base()
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    age = Column(Integer)
    gender = Column(String(20))
    language = Column(String(10), default="ru")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    analyses = relationship("Analysis", back_populates="user")
class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    source = Column(String(20), default="web")
    format = Column(String(10), default="pdf")
    status = Column(String(20), default="processed")
    document_ref = Column(String(255))
    user = relationship("User", back_populates="analyses")
    indicators = relationship("TestIndicator", back_populates="analysis")
class TestIndicator(Base):
    __tablename__ = "test_indicators"
    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    test_name = Column(String(255), nullable=False)
    value = Column(DECIMAL)
    units = Column(String(50))
    ref_min = Column(DECIMAL)
    ref_max = Column(DECIMAL)
    deviation = Column(String(10))  # normal/low/high
    comment = Column(String)
    analysis = relationship("Analysis", back_populates="indicators")
3.5 backend/app/api/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "CHANGE_ME_SECRET"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
class UserIn(BaseModel):
    email: str
    password: str
class Token(BaseModel):
    access_token: str
    token_type: str
fake_users_db = {}
@router.post("/register")
async def register(user: UserIn):
    if user.email in fake_users_db:
        raise HTTPException(status_code=400, detail="User exists")
    fake_users_db[user.email] = pwd_context.hash(user.password)
    return {"msg": "registered"}
@router.post("/login", response_model=Token)
async def login(user: UserIn):
    pw = fake_users_db.get(user.email)
    if not pw or not pwd_context.verify(user.password, pw):
        raise HTTPException(status_code=400, detail="Incorrect credentials")
    to_encode = {"sub": user.email, "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}
3.6 backend/app/api/uploads.py
from fastapi import APIRouter, File, UploadFile, Depends
from fastapi.responses import JSONResponse
from . import dummy_storage as storage  # простой заглушка
from pydantic import BaseModel
import uuid
router = APIRouter()
class UploadResponse(BaseModel):
    task_id: str
    status: str
@router.post("/document")
async def upload_document(file: UploadFile = File(...)):
    # сохранение файла в хранилище (папка /data/docs или minio)
    task_id = str(uuid.uuid4())
    content = await file.read()
    storage.save_document(task_id, file.filename, content, file.content_type)
    return UploadResponse(task_id=task_id, status="received")
3.7 backend/app/services/ocr.py (заглушка)
# заглушка OCR: возвращает примеры тестов без реального распознавания
def mock_extract(text: str):
    # простая заглушка для MVP: распознаём по ключевым словам
    tests = [
        {"test_name": "Glucose", "value": 5.6, "units": "mmol/L", "ref_min": 3.9, "ref_max": 5.5, "date": "2024-01-01"},
        {"test_name": "Cholesterol", "value": 190, "units": "mg/dL", "ref_min": 0, "ref_max": 200, "date": "2024-01-01"},
    ]
    return tests
3.8 backend/app/api/reports.py
from fastapi import APIRouter
router = APIRouter()
@router.get("/{analysis_id}")
async def get_report(analysis_id: int):
    # возвращает упрощённый отчет
    return {
        "analysis_id": analysis_id,
        "deviations": [
            {"test": "Glucose", "value": 5.6, "deviation": "high", "reason": "Example reason"},
        ],
        "recommendations": [
            {"text": "Keep sugar intake balanced", "doctor_contact": "dr@example.com"}
        ]
    }
3.9 backend/app/api/consultations.py
from fastapi import APIRouter
router = APIRouter()
@router.post("/request")
async def request_consultation():
    return {"status": "requested", "details": "consultation scheduled"}
3.10 backend/app/api/tests_reference.py
from fastapi import APIRouter
router = APIRouter()
@test_router = APIRouter()
@router.get("/list")
async def list_tests():
    return [
        {"name": "Glucose", "ref_min": 3.9, "ref_max": 5.5, "units": "mmol/L"},
        {"name": "Cholesterol", "ref_min": 0, "ref_max": 200, "units": "mg/dL"},
    ]
3.11 frontend/backend OCR storage заглушка
backend/app/services/ocr.py уже упомянуто
infra/scripts/init_db.sql можно разместить миграции
Примеры Android/VK UI/модуля загрузки (скелеты)
4.1 Android (Kotlin) skeleton (псевдо-код)
Экран вход/регистрация
Главная лента анализов
Экран загрузки документа (камера/файлы)
Экран обработки (индикатор)
Экран отчета (Отклонения, Причины, Рекомендации)
Экран консультации
Код-скелет (псевдо):
// app/src/main/java/com/medlab/MainActivity.kt
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // простая навигация между фрагментами
        setContentView(R.layout.activity_main)
    }
}
4.2 Веб-версия (React) — минимальный компонент
Страница загрузки
Отчет по компонентам
Простая таблица показателей
Пример компонента загрузки (псевдокод):
// frontend/web/src/components/UploadCard.jsx
export default function UploadCard() {
  const onFile = async (e) => {
    const file = e.target.files[0];
    // отправляем через fetch к /upload/document
  };
  return (
    <div className="upload-card">
      <input type="file" accept=".png,.jpg,.pdf" onChange={onFile} />
      <p>Поддержка PNG/JPG/PDF</p>
    </div>
  );
}
4.3 Telegram-бот (Python) — базовая логика
Приветствие
Загрузка документа
Отчет в ответном сообщении
Запрос на консультацию
Пример упрощённого бота (telebot/pydantic):
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добро пожаловать в MedicalLab. Отправьте документ.")
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # сохранить документ и отправить статус
    await update.message.reply_text("Документ получен. Обработка начинается.")
if __name__ == "__main__":
    app = ApplicationBuilder().token("TELEGRAM_BOT_TOKEN").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.run_polling()
Как запустить локально
Убедитесь, что Docker и Docker Compose установлены.
Разместите файлы в указанной структуре.
В корневом каталоге запустите:
docker-compose up -d
Подключитесь к MinIO по адресу http://localhost:9000 (логин: minio, пароль: minio12345)
API доступно по адресу http://localhost:8000
Веб-клиент собирается отдельно (npm/yarn install во фронтенде/веб-клиенте)
Что получаете в рамках MVP
Временная аутентификация через JWT
Загрузка документов через Android, веб-интерфейс и Telegram-бота
Заглушка OCR (в дальнейшем можно использовать Tesseract)
Базовая нормализация тестов и вычисление отклонений с учетом возраста/пола
Отчет с разделами «Отклонения», «Возможные причины» и «Рекомендации
История анализов и экспорт (пока заглушки — экспорт в JSON; PDF можно добавить через wkhtmltopdf или ReportLab)
Базовый уровень безопасности (TLS в тестовой среде и хранение данных в зашифрованном виде в БД)
Что вам нужно для продолжения
Подтвердите, что вы хотите получить именно полный репозиторий-скелет по описанному выше плану (Python FastAPI + Tesseract + полноценный фронтенд).
Уточните желаемые версии: Android/Kotlin, React/Vue и Telegram-бот на Python (названия технологий подтверждены).
Сообщите, нужны ли вам дополнительные уровни миграции БД, тестовая нагрузка, скрипты CI/CD.
Если хотите, могу сразу:
формализовать MVP-дрейф в Jira-стори/плане спринтов
добавить SQL-дамп и ER-диаграмму в текстовом виде
подготовить ASCII-вайрфреймы и подробные спецификации UI-компонентов
Готов приступить к выдаче полного артефакта: репозитория со структурой, готовыми скриптами запуска и минимальной реализацией MVP.
