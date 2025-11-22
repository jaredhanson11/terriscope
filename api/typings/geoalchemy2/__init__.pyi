from typing import Any

from sqlalchemy.types import UserDefinedType

class Geometry(UserDefinedType[Any]):
    def __init__(
        self,
        geometry_type: str | None = ...,
        srid: int = ...,
        dimension: int = ...,
        spatial_index: bool = ...,
        use_N_D_index: bool = ...,
        use_typmod: bool | None = ...,
        from_text: str | None = ...,
        name: str | None = ...,
        nullable: bool = ...,
        _spatial_index_reflected: Any = ...,
    ) -> None: ...
