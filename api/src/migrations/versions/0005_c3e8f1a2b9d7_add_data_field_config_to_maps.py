"""add data_field_config to maps.

Revision ID: c3e8f1a2b9d7
Revises: bd9a96a540db
Create Date: 2026-02-25 00:00:00.000000-08:00

"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from alembic import op as _op

if TYPE_CHECKING:
    from geoalchemy2.alembic_helpers import GeoAlchemyOperations

    op: GeoAlchemyOperations = cast("GeoAlchemyOperations", _op)
else:
    op = _op  # type: ignore[assignment]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3e8f1a2b9d7"
down_revision: str | None = "bd9a96a540db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade revisions: bd9a96a540db to c3e8f1a2b9d7."""
    op.add_column(
        "maps",
        sa.Column(
            "data_field_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade revisions: c3e8f1a2b9d7 to bd9a96a540db."""
    op.drop_column("maps", "data_field_config")
