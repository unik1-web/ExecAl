import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from .models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://medical:medicalpass@postgres:5432/medicallab",
)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    # MVP-упрощение: создаём таблицы автоматически.
    # Для продакшена лучше Alembic-миграции.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # MVP: "лёгкая миграция" для уже созданной БД (create_all не меняет типы колонок).
        # application/pdf > 10 символов, поэтому расширяем колонку.
        await conn.execute(text("ALTER TABLE IF EXISTS analyses ALTER COLUMN format TYPE VARCHAR(100)"))


async def get_session():
    async with async_session() as session:
        yield session

