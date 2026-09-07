from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    database: Literal["connected"]


@router.get("/health", response_model=HealthResponse, summary="Check API and database connectivity")
def health_check(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        logger.exception("Database health check failed")
        raise ApiError(503, "database_unavailable", "The database is currently unavailable.") from error
    return HealthResponse(status="ok", service="api", database="connected")
