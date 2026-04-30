"""Invite routers — map-scoped (owner manages invites) and me-scoped (user acts on their own invites)."""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from src.app.database import DatabaseSession
from src.models.accounts import UserModel
from src.models.graph import MapModel
from src.models.permissions import MapInviteModel, UserMapRoleModel
from src.schemas.invites import CreateInviteDTO, MapInvite, MapInviteWithMap
from src.services.auth import CurrentUserDependency
from src.services.permissions import PermissionsServiceDependency

logger = logging.getLogger(__name__)

# ── Map-scoped: /maps/{map_id}/invites ────────────────────────────────────

map_invites_router = APIRouter(prefix="/maps/{map_id}/invites", tags=["Invites"])


def _require_owner(map_id: str, current_user_id: int, permission_service: PermissionsServiceDependency) -> None:
    if not permission_service.check_for_map_access(
        user_id=current_user_id, map_id=map_id, map_roles=["OWNER"]
    ):
        raise HTTPException(status_code=403, detail="Only the map owner can manage invites")


@map_invites_router.get("", response_model=list[MapInvite])
def list_map_invites(
    map_id: str,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> list[MapInvite]:
    """List pending invites for a map. Owner only."""
    _require_owner(map_id, current_user.id, permission_service)

    invites = (
        db.execute(
            select(MapInviteModel)
            .where(MapInviteModel.map_id == map_id, MapInviteModel.status == "pending")
        )
        .scalars()
        .all()
    )

    inviter_ids = list({i.invited_by_user_id for i in invites})
    inviters: dict[int, UserModel] = {}
    if inviter_ids:
        rows = db.execute(select(UserModel).where(UserModel.id.in_(inviter_ids))).scalars().all()
        inviters = {u.id: u for u in rows}

    return [
        MapInvite(
            id=inv.id,
            map_id=inv.map_id,
            invited_email=inv.invited_email,
            invited_by_name=inviters[inv.invited_by_user_id].name if inv.invited_by_user_id in inviters else None,
            invited_by_email=inviters[inv.invited_by_user_id].email if inv.invited_by_user_id in inviters else "",
            status=inv.status,
        )
        for inv in invites
    ]


@map_invites_router.post("", response_model=MapInvite, status_code=201)
def create_invite(
    map_id: str,
    body: CreateInviteDTO,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> MapInvite:
    """Invite a user by email to a map. Owner only."""
    _require_owner(map_id, current_user.id, permission_service)

    email = str(body.email).lower()

    # Reject if the email already belongs to a map member
    existing_user = db.execute(select(UserModel).where(UserModel.email == email)).scalars().first()
    if existing_user:
        already_member = db.execute(
            select(UserMapRoleModel).where(
                UserMapRoleModel.map_id == map_id,
                UserMapRoleModel.user_id == existing_user.id,
            )
        ).scalars().first()
        if already_member:
            raise HTTPException(status_code=409, detail="User is already a member of this map")

    # Reject duplicate pending invite
    existing_invite = db.execute(
        select(MapInviteModel).where(
            MapInviteModel.map_id == map_id,
            MapInviteModel.invited_email == email,
            MapInviteModel.status == "pending",
        )
    ).scalars().first()
    if existing_invite:
        raise HTTPException(status_code=409, detail="A pending invite already exists for this email")

    invite = MapInviteModel(
        map_id=map_id,
        invited_email=email,
        invited_by_user_id=current_user.id,
        status="pending",
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return MapInvite(
        id=invite.id,
        map_id=invite.map_id,
        invited_email=invite.invited_email,
        invited_by_name=current_user.name,
        invited_by_email=current_user.email,
        status=invite.status,
    )


@map_invites_router.delete("/{invite_id}", status_code=204)
def revoke_invite(
    map_id: str,
    invite_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> None:
    """Revoke a pending invite. Owner only."""
    _require_owner(map_id, current_user.id, permission_service)

    invite = db.execute(
        select(MapInviteModel).where(
            MapInviteModel.id == invite_id,
            MapInviteModel.map_id == map_id,
        )
    ).scalars().first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != "pending":
        raise HTTPException(status_code=409, detail="Invite is no longer pending")

    db.delete(invite)
    db.commit()


# ── Me-scoped: /me/invites ────────────────────────────────────────────────

me_invites_router = APIRouter(prefix="/me/invites", tags=["Invites"])


@me_invites_router.get("", response_model=list[MapInviteWithMap])
def list_my_invites(
    db: DatabaseSession,
    current_user: CurrentUserDependency,
) -> list[MapInviteWithMap]:
    """List pending invites for the current user's email."""
    invites = (
        db.execute(
            select(MapInviteModel).where(
                MapInviteModel.invited_email == current_user.email,
                MapInviteModel.status == "pending",
            )
        )
        .scalars()
        .all()
    )

    if not invites:
        return []

    map_ids = list({i.map_id for i in invites})
    maps = db.execute(select(MapModel).where(MapModel.id.in_(map_ids))).scalars().all()
    maps_by_id = {m.id: m for m in maps}

    inviter_ids = list({i.invited_by_user_id for i in invites})
    inviters_rows = db.execute(select(UserModel).where(UserModel.id.in_(inviter_ids))).scalars().all()
    inviters = {u.id: u for u in inviters_rows}

    return [
        MapInviteWithMap(
            id=inv.id,
            map_id=inv.map_id,
            map_name=maps_by_id[inv.map_id].name if inv.map_id in maps_by_id else "(unknown map)",
            invited_by_name=inviters[inv.invited_by_user_id].name if inv.invited_by_user_id in inviters else None,
            invited_by_email=inviters[inv.invited_by_user_id].email if inv.invited_by_user_id in inviters else "",
            status=inv.status,
        )
        for inv in invites
        if inv.map_id in maps_by_id
    ]


@me_invites_router.post("/{invite_id}/accept", status_code=204)
def accept_invite(
    invite_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> None:
    """Accept a pending invite. Grants MEMBER access and marks the invite accepted."""
    invite = db.execute(
        select(MapInviteModel).where(
            MapInviteModel.id == invite_id,
            MapInviteModel.invited_email == current_user.email,
            MapInviteModel.status == "pending",
        )
    ).scalars().first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    permission_service.add_map_role(user_id=current_user.id, map_id=invite.map_id, role="MEMBER")
    invite.status = "accepted"
    db.commit()


@me_invites_router.post("/{invite_id}/decline", status_code=204)
def decline_invite(
    invite_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
) -> None:
    """Decline a pending invite."""
    invite = db.execute(
        select(MapInviteModel).where(
            MapInviteModel.id == invite_id,
            MapInviteModel.invited_email == current_user.email,
            MapInviteModel.status == "pending",
        )
    ).scalars().first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    invite.status = "declined"
    db.commit()
