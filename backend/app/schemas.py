from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    age: int | None = None
    gender: str | None = None
    language: str = "ru"


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

