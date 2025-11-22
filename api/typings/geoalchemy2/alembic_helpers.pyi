from collections.abc import Iterable, Sequence
from typing import Any, Literal

from alembic.autogenerate.api import AutogenContext
from alembic.migration import MigrationContext
from alembic.operations.base import Operations
from alembic.operations.ops import MigrationScript
from sqlalchemy import Column, ColumnElement, TextClause
from sqlalchemy.schema import SchemaItem

def writer(
    context: MigrationContext,
    revision: str | Iterable[str | None] | Iterable[str],
    directives: list[MigrationScript],
) -> None: ...
def include_object(
    obj: SchemaItem,
    name: str | None,
    obj_type: Literal[
        "schema",
        "table",
        "column",
        "index",
        "unique_constraint",
        "foreign_key_constraint",
    ],
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool: ...
def render_item(obj_type: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]: ...

class GeoAlchemyOperations(Operations):
    def add_geospatial_column(
        self,
        table_name: str,
        column: Column[Any],
        schema: str | None = ...,
    ) -> Any: ...
    def drop_geospatial_column(self, table_name: str, column_name: str, schema: str | None = ..., **kw: Any) -> Any: ...
    def create_geospatial_table(self, table_name: str, *columns: SchemaItem, **kw: Any) -> Any: ...
    def drop_geospatial_table(self, table_name: str, schema: str | None = ..., **kw: Any) -> Any: ...
    def from_table_drop_geospatial_table(self, table: Any, _namespace_metadata: Any = ...) -> Any: ...
    def create_geospatial_index(
        self,
        index_name: str,
        table_name: str,
        columns: Sequence[str | TextClause | ColumnElement[Any]],
        schema: str | None = ...,
        unique: bool = ...,
        **kw: Any,
    ) -> Any: ...
    def drop_geospatial_index(
        self,
        index_name: str,
        table_name: str,
        column_name: str,
        schema: str | None = ...,
        unique: bool = ...,
        **kw: Any,
    ) -> Any: ...
    def from_index_drop_geospatial_index(self, index: Any) -> Any: ...
