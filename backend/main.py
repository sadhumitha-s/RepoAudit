"""
RepoAudit API entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers.audit import router as audit_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("RepoAudit API starting up")
    yield
    logging.info("RepoAudit API shutting down")


app = FastAPI(
    title="RepoAudit",
    description="Automated ML repository reproducibility auditor",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
origins = [o.strip() for o in settings.allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(audit_router)


@app.get("/health")
async def health():
    return {"status": "ok"}