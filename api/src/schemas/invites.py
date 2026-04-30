"""Invite and member schemas."""

from pydantic import BaseModel, EmailStr

from src.models.permissions import InviteStatus, MapRole


class MapMember(BaseModel):
    """A user who has accepted access to a map."""

    user_id: int
    name: str | None
    email: str
    role: MapRole


class MapInvite(BaseModel):
    """Pending invite as seen by the map owner."""

    id: int
    map_id: str
    invited_email: str
    invited_by_name: str | None
    invited_by_email: str
    status: InviteStatus


class MapInviteWithMap(BaseModel):
    """Pending invite as seen by the invited user — includes map context."""

    id: int
    map_id: str
    map_name: str
    invited_by_name: str | None
    invited_by_email: str
    status: InviteStatus


class CreateInviteDTO(BaseModel):
    """Request body for creating a map invite."""

    email: EmailStr
