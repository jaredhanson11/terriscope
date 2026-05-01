"""Members router — list and remove active map members."""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from src.app.database import DatabaseSession
from src.models.accounts import UserModel
from src.models.permissions import UserMapRoleModel
from src.schemas.invites import MapMember
from src.services.auth import CurrentUserDependency
from src.services.permissions import PermissionsServiceDependency

logger = logging.getLogger(__name__)

map_members_router = APIRouter(prefix="/maps/{map_id}/members", tags=["Members"])


@map_members_router.get("", response_model=list[MapMember])
def list_members(
    map_id: str,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> list[MapMember]:
    """List active members for a map. Accessible to all members."""
    if not permission_service.check_for_map_access(
        user_id=current_user.id, map_id=map_id, map_roles=["OWNER", "MEMBER"]
    ):
        raise HTTPException(status_code=404, detail="Map not found")

    roles = (
        db.execute(select(UserMapRoleModel).where(UserMapRoleModel.map_id == map_id))
        .scalars()
        .all()
    )

    user_ids = [r.user_id for r in roles]
    users = db.execute(select(UserModel).where(UserModel.id.in_(user_ids))).scalars().all()
    users_by_id = {u.id: u for u in users}

    return [
        MapMember(
            user_id=r.user_id,
            name=users_by_id[r.user_id].name if r.user_id in users_by_id else None,
            email=users_by_id[r.user_id].email if r.user_id in users_by_id else "",
            role=r.role,
        )
        for r in roles
    ]


@map_members_router.delete("/{user_id}", status_code=204)
def remove_member(
    map_id: str,
    user_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> None:
    """Remove a member from a map. Any map member. Cannot remove yourself."""
    if not permission_service.check_for_map_access(
        user_id=current_user.id, map_id=map_id, map_roles=["OWNER", "MEMBER"]
    ):
        raise HTTPException(status_code=403, detail="No access to this map")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot remove yourself from the map")

    role = db.execute(
        select(UserMapRoleModel).where(
            UserMapRoleModel.map_id == map_id,
            UserMapRoleModel.user_id == user_id,
        )
    ).scalars().first()

    if not role:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(role)
    db.commit()
