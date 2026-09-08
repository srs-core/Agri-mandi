from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.logging import configure_logging
from app.db.migrate_negotiation import migrate_negotiation_schema
from app.db.session import SessionLocal
from app.modules.auth.service import ensure_system_roles
from app.modules.marketplace.service import ensure_system_commodities

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    migrate_negotiation_schema()
    with SessionLocal() as db:
        ensure_system_roles(db)
        ensure_system_commodities(db)
    yield


app = FastAPI(title=settings.project_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    content: dict[str, object] = {"error": {"code": exc.code, "message": exc.message}}
    if exc.details is not None:
        content["error"]["details"] = exc.details  # type: ignore[index]
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Request validation failed.", "details": details}},
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Unhandled database error", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "database_unavailable", "message": "The database is currently unavailable."}},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
    )
