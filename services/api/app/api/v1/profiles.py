from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.marketplace.service import (
    get_user_profile,
    submit_verification_request,
    update_user_profile,
)
from app.schemas.marketplace import (
    ProfileUpdateRequest,
    UserProfileResponse,
    VerificationCreateRequest,
    VerificationRequestResponse,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=UserProfileResponse, summary="Get current user's profile and primary location")
def get_my_profile(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> UserProfileResponse:
    return get_user_profile(db, current_user)


@router.put("/me", response_model=UserProfileResponse, summary="Update current user's profile and primary location")
def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> UserProfileResponse:
    return update_user_profile(db, current_user, payload)


@router.post("/verification-request", response_model=VerificationRequestResponse, summary="Submit a profile verification request")
def request_verification(
    payload: VerificationCreateRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationRequestResponse:
    return submit_verification_request(db, current_user, payload)
