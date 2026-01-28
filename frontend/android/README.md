# Android (Kotlin) — MVP приложение

Это минимальный Android-клиент для ExecAl:

- регистрация / логин (JWT)
- загрузка PDF/PNG/JPG в backend (`/upload/document`)
- просмотр JSON отчёта (`/report/{id}`)
- скачивание PDF отчёта (`/report/{id}/pdf`) через системный диалог сохранения

## Как запустить

1) Подними backend локально:

- `docker compose up -d --build backend`

2) Открой папку `frontend/android` в Android Studio (Giraffe+ / Iguana+).

3) Запусти на эмуляторе.

## Настройка API base

По умолчанию приложение ходит в:

- **эмулятор**: `http://10.0.2.2:8000` (это “хост” для Android Emulator, где у тебя крутится Docker)

Если запускаешь на реальном устройстве — укажи IP твоего ПК в одной сети, например:

- `http://192.168.1.10:8000`

Это поле можно поменять прямо в UI (поле **API base**).


