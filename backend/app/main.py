"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.ai import AIError
from app.config import get_settings
from app.db import engine
from app.routers import auth, catalog, notes, questions
from app.seed.seed import ensure_seeded

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(get_settings().upload_dir).mkdir(parents=True, exist_ok=True)
    ensure_seeded()
    yield


app = FastAPI(
    title="myClassBoard-LMS: AI Learning Assistant",
    description="POC API. All data is synthetic.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # lets the browser read the download filename
)


@app.exception_handler(AIError)
async def ai_error_handler(_: Request, exc: AIError) -> JSONResponse:
    """Any AI failure reaches the UI as a friendly 503, never a stack trace."""
    return JSONResponse(status_code=503, content={"detail": exc.message})


@app.get("/api/health", tags=["health"])
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(notes.router)
app.include_router(questions.router)
