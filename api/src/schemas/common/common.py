"""Common utility schemas and helpers."""

from typing import TypeVar

from attr import dataclass

T = TypeVar("T")


@dataclass
class ByUtility[T]:
    """Common by utility type."""

    electricity: T
    steam: T
    gas: T
    chilled_water: T
