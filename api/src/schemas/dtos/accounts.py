"""Accounts DTOs."""

from pydantic import BaseModel


class UpdateMeDTO(BaseModel):
    """PATCH body for updating the current user's profile."""

    name: str | None = None
    avatar_url: str | None = None
