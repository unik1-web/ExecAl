import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, consultations, reports, tests_reference, uploads
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="MedicalLab Backend", lifespan=lifespan)

cors_origins_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(uploads.router, prefix="/upload", tags=["uploads"])
app.include_router(reports.router, prefix="/report", tags=["reports"])
app.include_router(consultations.router, prefix="/consultation", tags=["consultations"])
app.include_router(tests_reference.router, prefix="/tests", tags=["tests_reference"])


@app.get("/")
async def root():
    return {"status": "ok", "message": "Medical Lab MVP Backend"}

