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

## Как собрать APK

### Debug APK

- Команда: `.\gradlew.bat :app:assembleDebug`
- Файл: `app/build/outputs/apk/debug/app-debug.apk`

### Release APK (подпись через keystore)

1) Создай keystore (если ещё нет):

- `keytool -genkeypair -v -keystore execal-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias execal`

2) Собери release, передав пароли через переменные окружения:

```powershell
$env:EXECAL_KEYSTORE_PATH = \"D:\\Documents\\GitHub\\ExecAl\\frontend\\android\\execal-release.jks\"
$env:EXECAL_KEYSTORE_PASSWORD = \"<пароль_keystore>\"
$env:EXECAL_KEY_ALIAS = \"execal\"
$env:EXECAL_KEY_PASSWORD = \"<пароль_ключа>\"  # если совпадает с keystore — можно не задавать
.\gradlew.bat :app:assembleRelease
```

- Файл: `app/build/outputs/apk/release/app-release.apk`

## Настройка API base

По умолчанию приложение ходит в:

- **эмулятор**: `http://10.0.2.2:8000` (это “хост” для Android Emulator, где у тебя крутится Docker)

Если запускаешь на реальном устройстве — укажи IP твоего ПК в одной сети, например:

- `http://192.168.1.10:8000`

Это поле можно поменять прямо в UI (поле **API base**).


