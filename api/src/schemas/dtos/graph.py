"""Graph dtos."""

from pydantic import BaseModel, field_validator


class CreateLayer(BaseModel):
    """CreateLayer."""

    name: str
    map_id: int


class UpdateNode(BaseModel):
    """UpdateNode."""

    parent_node_id: int | None
    name: str
    color: str


class BulkUpdateNode(UpdateNode):
    """BulkUpdateNode."""

    id: int


class CreateNode(UpdateNode):
    """CreateNode."""

    layer_id: int


class AssignZip(BaseModel):
    """Assign or update a single zip code's territory assignment.

    PUT with parent_node_id=null unassigns the zip (nulls the FK, preserves the row and color).
    DELETE /layers/{layer_id}/zips/{zip_code} resets the zip (removes the row entirely).
    """

    parent_node_id: int | None
    color: str | None = None
    """Optional color override. If omitted on first assignment, copied from geography_zip_codes.color."""


class BulkAssignZips(BaseModel):
    """Bulk assign or unassign a list of zip codes to a territory.

    Primary operation after lasso selection: select zips on map, assign to territory.
    parent_node_id=null unassigns all provided zip codes (preserves rows and colors).
    """

    zip_codes: list[str]
    parent_node_id: int | None
    color: str | None = None
    """Optional color override applied to all zip codes in the batch."""

    @field_validator("zip_codes")
    @classmethod
    def pad_zip_codes(cls, v: list[str]) -> list[str]:
        """Ensure zip codes are always zero-padded to 5 characters."""
        return [z.zfill(5) for z in v]
