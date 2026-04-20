"""Me routes."""

import logging

from fastapi import APIRouter

from src.app.database import DatabaseSession
from src.schemas.accounts import User
from src.schemas.dtos.accounts import UpdateMeDTO
from src.services.auth import CurrentUserDependency

accounts_router = APIRouter(
    prefix="/me",
    tags=["Me"],
)

logger = logging.getLogger(__name__)


@accounts_router.get("", response_model=User)
def get_me(
    current_user: CurrentUserDependency,
):
    """Get the currently logged in user."""
    return User(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
    )


@accounts_router.patch("", response_model=User)
def update_me(
    body: UpdateMeDTO,
    current_user: CurrentUserDependency,
    db: DatabaseSession,
):
    """Update the current user's name."""
    current_user.name = body.name
    db.commit()
    return User(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
    )


@accounts_router.post("/request-password-reset", response_model=None, status_code=202)
def request_password_reset(
    current_user: CurrentUserDependency,
):
    """Send a password reset email to the current user."""
    # TODO: integrate with email provider
    logger.info("Password reset requested for user %s", current_user.email)
    return {"message": "If this email is registered, a reset link has been sent."}
