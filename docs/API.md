# API (MVP)

Базовый URL: `http://localhost:8000`

## Auth

- `POST /auth/register`
  - body: `{ "email": "...", "password": "...", "age": 30, "gender": "male", "language": "ru" }`
- `POST /auth/login`
  - body: `{ "email": "...", "password": "..." }`
  - response: `{ "access_token": "...", "token_type": "bearer" }`

## Uploads

- `POST /upload/document`
  - multipart/form-data: `file`
  - header: `Authorization: Bearer <token>`
  - response: `{ "analysis_id": 1, "status": "processed" }`

- `GET /upload/history`
  - header: `Authorization: Bearer <token>`

## Reports

- `GET /report/{analysis_id}`
  - header: `Authorization: Bearer <token>`
- `GET /report/{analysis_id}/pdf`
  - header: `Authorization: Bearer <token>`
  - response: `application/pdf`

## Consultations

- `POST /consultation/request`
  - header: `Authorization: Bearer <token>`

## Tests reference

- `GET /tests/list`

