"""Permissions service module."""

import logging
from typing import Annotated

from fastapi import Depends

from src.app.database import DatabaseSession
from src.models.permissions import MapRole, UploadRole, UserMapRoleModel, UserUploadRoleModel

from .base import BaseService

logger = logging.getLogger(__name__)


class PermissionService(BaseService):
    """Permission service."""

    def add_map_role(self, user_id: int, map_id: str, role: MapRole) -> UserMapRoleModel:
        """Add a map role to a user."""
        user_map_role = UserMapRoleModel(
            role=role,
            user_id=user_id,
            map_id=map_id,
        )
        self.db.add(user_map_role)
        self.db.flush()
        return user_map_role

    def remove_map_role(self, user_id: int, map_id: int):
        """Remove a roles from a user for a given map."""
        self.db.query(UserMapRoleModel).filter_by(user_id=user_id, map_id=map_id).delete()
        self.db.flush()

    def update_map_role(self, user_id: int, map_id: str, role: MapRole) -> UserMapRoleModel:
        """Update a map role for a user."""
        user_map_role = self.db.query(UserMapRoleModel).filter_by(user_id=user_id, map_id=map_id).one()
        user_map_role.role = role
        self.db.flush()
        return user_map_role

    def check_for_map_access(
        self,
        user_id: int,
        map_id: str,
        map_roles: list[MapRole],
    ) -> bool:
        """Check if the user has any of the roles in the list."""
        map_role = self.db.query(UserMapRoleModel).filter(
            UserMapRoleModel.user_id == user_id,
            UserMapRoleModel.map_id == map_id,
            UserMapRoleModel.role.in_(map_roles),
        )
        return map_role.count() > 0

    def list_map_roles(
        self,
        user_id: int,
    ) -> list[UserMapRoleModel]:
        """List map roles for a user."""
        return self.db.query(UserMapRoleModel).filter_by(user_id=user_id).all()

    def add_upload_role(self, user_id: int, upload_id: str, role: UploadRole = "OWNER") -> UserUploadRoleModel:
        """Grant a user access to an upload."""
        record = UserUploadRoleModel(user_id=user_id, upload_id=upload_id, role=role)
        self.db.add(record)
        self.db.flush()
        return record

    def check_for_upload_access(self, user_id: int, upload_id: str) -> bool:
        """Return True if the user has any role on the upload."""
        return (
            self.db.query(UserUploadRoleModel)
            .filter_by(user_id=user_id, upload_id=upload_id)
            .count()
            > 0
        )


def _get_permission_service_dependency(db: DatabaseSession) -> PermissionService:
    """Get permission service dependency."""
    return PermissionService(db=db)


PermissionsServiceDependency = Annotated[PermissionService, Depends(_get_permission_service_dependency)]
