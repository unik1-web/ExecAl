from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import auth, consultations, reports, tests_reference, uploads
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="MedicalLab Backend", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(uploads.router, prefix="/upload", tags=["uploads"])
app.include_router(reports.router, prefix="/report", tags=["reports"])
app.include_router(consultations.router, prefix="/consultation", tags=["consultations"])
app.include_router(tests_reference.router, prefix="/tests", tags=["tests_reference"])


@app.get("/")
async def root():
    return {"status": "ok", "message": "Medical Lab MVP Backend"}

