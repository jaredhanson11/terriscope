"""Utilities functions for alembic.

Utility functions specific to alembic configuration. Things like
migration hooks, etc can be placed here.
"""

import re
from collections.abc import Collection, Iterable, Mapping, MutableMapping
from pathlib import Path
from typing import Any, Literal

import sqlalchemy
from alembic.migration import MigrationContext, MigrationInfo
from alembic.operations import Operations
from alembic.operations.ops import MigrationScript
from geoalchemy2 import alembic_helpers


def process_revision_directives(
    context: MigrationContext,
    revision: str | Iterable[str | None] | Iterable[str],
    directives: list[MigrationScript],
):
    """Process revision file name.

    This function will create auto incrementing alembic migration filenames that
    still include the slug in them. Inspiration found here: https://stackoverflow.com/a/79014518
    """
    script_directory = context.opts["revision_context"].script_directory
    head_revision_id = script_directory.get_current_head()
    revision_num = 1
    if head_revision_id:
        head_revision_obj = script_directory.get_revision(head_revision_id)
        head_revision_prefix, _ = Path(head_revision_obj.path).name.split("_", 1)
        head_revision_num = re.findall(r"^(\d+)", head_revision_prefix)
        head_revision_num = int(head_revision_num[0]) if head_revision_num else 0
        revision_num = head_revision_num + 1
    revision_num_str = "0" * (4 - len(str(revision_num))) + f"{revision_num}"
    file_template_parts = script_directory.file_template.split("_", 1)
    if re.findall(r"^\d+", file_template_parts[0]):
        file_template = f"{revision_num_str}_{file_template_parts[1]}"
    else:
        file_template = f"{revision_num_str}_{script_directory.file_template}"
    script_directory.file_template = file_template
    # Add in geoalchemy helpers according to https://geoalchemy-2.readthedocs.io/en/latest/alembic.html#helpers
    alembic_helpers.writer(context=context, revision=revision, directives=directives)


def update_history(ctx: MigrationContext, step: MigrationInfo, heads: Collection[Any], run_args: Mapping[str, Any]):
    """Update history in alembic_version_history.

    This function automatically inserts an upgrade/downgrade record into the alembic version log table.
    This function comes from inspiration here: https://stackoverflow.com/questions/73248731/alembic-store-extra-information-in-alembic-version-table
    """

    def _get_revision_message(revision: Any) -> str:
        """Get revision doc message.

        arg revisions is Any here to avoid import error.
        """
        return revision.doc

    message = ""
    revision_type = "UPGRADE" if step.is_upgrade else "DOWNGRADE"
    revision_id = "<unknown>"
    if step.is_upgrade and step.up_revision:
        revision_id = step.up_revision_id
        message: str = _get_revision_message(step.up_revision)
    elif not step.is_upgrade and step.down_revisions:
        revision_id = step.down_revision_ids[0]
        if step.down_revisions[0]:
            message: str = _get_revision_message(step.down_revisions[0])
    op = Operations(ctx)
    op.execute(
        sqlalchemy.sql.text(
            "INSERT INTO alembic_version_history (version_num, message, type) VALUES (:version_num, :message, :type)",
        ).bindparams(version_num=revision_id, message=message, type=revision_type),
    )


def include_name(
    name: str | None,
    type_: Literal[
        "schema",
        "table",
        "column",
        "index",
        "unique_constraint",
        "foreign_key_constraint",
    ],
    parent_names: MutableMapping[
        Literal[
            "schema_name",
            "table_name",
            "schema_qualified_table_name",
        ],
        str | None,
    ],
) -> bool:
    """Don't update alembic_version_history table in migration.

    This function comes from inspiration here: https://stackoverflow.com/questions/73248731/alembic-store-extra-information-in-alembic-version-table
    """
    return not (type_ == "table" and name == "alembic_version_history")
