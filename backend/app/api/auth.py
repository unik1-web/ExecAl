from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import User
from ..schemas import Token, UserCreate, UserLogin, UserPublic
from ..services.security import create_access_token, hash_password, verify_password

router = APIRouter()


@router.post("/register", response_model=UserPublic)
async def register(user: UserCreate, session: AsyncSession = Depends(get_session)):
    exists = await session.scalar(select(User).where(User.email == user.email))
    if exists:
        raise HTTPException(status_code=400, detail="User exists")

    db_user = User(
        email=user.email,
        password_hash=hash_password(user.password),
        age=user.age,
        gender=user.gender,
        language=user.language,
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return UserPublic(
        id=db_user.id,
        email=db_user.email,
        age=db_user.age,
        gender=db_user.gender,
        language=db_user.language,
        created_at=db_user.created_at,
    )


@router.post("/login", response_model=Token)
async def login(user: UserLogin, session: AsyncSession = Depends(get_session)):
    db_user = await session.scalar(select(User).where(User.email == user.email))
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect credentials")
    token = create_access_token(subject=db_user.email)
    return Token(access_token=token, token_type="bearer")

