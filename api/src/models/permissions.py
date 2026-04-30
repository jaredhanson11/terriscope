"""Permissions models."""

from typing import Literal

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from .base import Base, TimestampMixin, intpk

MapRole = Literal["OWNER", "MEMBER"]
UploadRole = Literal["OWNER"]
InviteStatus = Literal["pending", "accepted", "declined"]


class UserUploadRoleModel(Base, TimestampMixin):
    """Associates a user with a map upload. Mirrors UserMapRoleModel for upload access control."""

    __tablename__ = "user_upload_roles"

    id: Mapped[intpk] = mapped_column(Integer, primary_key=True, autoincrement=True, init=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id: Mapped[str] = mapped_column(PgUUID(as_uuid=False), ForeignKey("map_uploads.id"), nullable=False)
    role: Mapped[UploadRole]

    @declared_attr.directive
    def __table_args__(cls):
        """Table args for UserUploadRoleModel."""
        return (
            UniqueConstraint("user_id", "upload_id"),
            Index("idx_user_upload_roles_user_id", "user_id"),
        )


class UserMapRoleModel(Base, TimestampMixin):
    """UserMapRoleModel."""

    __tablename__ = "user_map_roles"

    id: Mapped[intpk] = mapped_column(Integer, primary_key=True, autoincrement=True, init=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    map_id: Mapped[str] = mapped_column(PgUUID(as_uuid=False), ForeignKey("maps.id"), nullable=False)
    role: Mapped[MapRole]

    @declared_attr.directive
    def __table_args__(cls):
        """Table args for UserMapRoleModel."""
        owner: MapRole = "OWNER"
        return (
            UniqueConstraint("user_id", "role", "map_id"),
            Index("uq_map_owner", "map_id", unique=True, postgresql_where=text(f"role = '{owner}'")),
        )


class MapInviteModel(Base, TimestampMixin):
    """Invite record keyed on email so it can target users who haven't registered yet."""

    __tablename__ = "map_invites"

    id: Mapped[intpk] = mapped_column(Integer, primary_key=True, autoincrement=True, init=False)
    map_id: Mapped[str] = mapped_column(PgUUID(as_uuid=False), ForeignKey("maps.id"), nullable=False)
    invited_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    invited_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[InviteStatus] = mapped_column(default="pending")

    @declared_attr.directive
    def __table_args__(cls):
        """Table args for MapInviteModel."""
        pending: InviteStatus = "pending"
        return (
            # Partial unique: only pending invites must be unique per (map, email).
            # Declined rows are kept as history and do not block re-inviting.
            Index(
                "uq_map_invites_pending",
                "map_id",
                "invited_email",
                unique=True,
                postgresql_where=text(f"status = '{pending}'"),
            ),
            Index("idx_map_invites_invited_email", "invited_email"),
            Index("idx_map_invites_map_id", "map_id"),
        )
