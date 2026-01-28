from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    age: int | None = None
    gender: str | None = None
    language: str = "ru"

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, v: str) -> str:
        # bcrypt ограничивает пароль 72 байтами (после utf-8 кодирования).
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be <= 72 bytes (bcrypt limit)")
        return v


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    age: int | None = None
    gender: str | None = None
    language: str = "ru"
    created_at: datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be <= 72 bytes (bcrypt limit)")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UploadResponse(BaseModel):
    analysis_id: int
    status: str


class Indicator(BaseModel):
    test_name: str
    value: Decimal | None = None
    units: str | None = None
    ref_min: Decimal | None = None
    ref_max: Decimal | None = None
    deviation: str | None = None
    comment: str | None = None


class Report(BaseModel):
    analysis_id: int
    deviations: list[dict]
    recommendations: list[dict]
    indicators: list[Indicator] = []

