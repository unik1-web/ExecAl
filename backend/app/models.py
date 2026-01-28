from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="ru")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    analyses: Mapped[list[Analysis]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(20), default="web")
    # content-type вроде application/pdf не помещается в 10 символов
    format: Mapped[str] = mapped_column(String(100), default="file")
    status: Mapped[str] = mapped_column(String(20), default="received")  # received/processed/failed

    document_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)  # minio object key
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="analyses")
    indicators: Mapped[list[TestIndicator]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class TestIndicator(Base):
    __tablename__ = "test_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )

    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    units: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ref_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    deviation: Mapped[str | None] = mapped_column(String(10), nullable=True)  # normal/low/high
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis: Mapped[Analysis] = relationship(back_populates="indicators")

