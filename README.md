# ExecAl

MVP: **Python 3.11 + FastAPI + PostgreSQL + MinIO + Tesseract OCR (PNG/JPG) + PDF-отчёт**.

## Быстрый старт

### Локальная разработка (рекомендуется)

- **Только API + БД + MinIO**:
  - `docker compose up --build`
- **С фронтендом**:
  - `docker compose --profile web up --build`
- **С Telegram-ботом**:
  - `TELEGRAM_BOT_TOKEN=xxx docker compose --profile telegram up --build`

### Prod/Staging (гибридный подход)

- `docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build`

### Makefile (шорткаты)

- `make up`
- `make up-all`
- `make up-prod`

### Полезное

- **API**: `http://localhost:8000` (Swagger: `/docs`)
- **MinIO Console**: `http://localhost:9001` (minio / minio12345)
- **Пример env**: `env.example` (можно скопировать в `.env`)

### Про MinIO Console и почему там не подходят пользователи из web

- **MinIO — это отдельное S3-хранилище**, у него **свои** учётные данные (`MINIO_ROOT_USER/MINIO_ROOT_PASSWORD` в `docker-compose.yml`).
- Пользователи, которых ты создаёшь через web (`/auth/register`), — это **пользователи приложения** (JWT) и **не связаны** с MinIO.
- В консоли MinIO (по умолчанию `http://localhost:9001`) логин/пароль: **minio / minio12345**.

### Почему результаты анализа раньше были одинаковые

- Раньше для `application/pdf` не было OCR, и код часто уходил в одинаковую MVP-заглушку показателей.
- Сейчас добавлен OCR для PDF/картинок и общий парсер строк, чтобы результат зависел от содержимого документа.

### Если зависает `npm install` при сборке web

- Можно указать npm registry/зеркало (Docker build args):
  - `NPM_REGISTRY=https://registry.npmjs.org/ docker compose --profile web build --no-cache web`
- Или положить `NPM_REGISTRY=...` в `.env` (см. `env.example`)
