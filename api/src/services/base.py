"""Base service module and root level dependencies."""

from typing import Literal

from src.app.database import DatabaseSession
from src.models.base import Base


class BaseService:
    """Base service class."""

    db: DatabaseSession

    def __init__(self, db: DatabaseSession):
        """Initialize the service with the database session."""
        self.db = db


class RecordNotFoundError(Exception):
    """Exception raised when a record is not found.

    This exception should only be thrown when a record is expected to exist but does not.
    This means that the query made causing this exception should be filtering for one specific
    record by its ID or other unique fields on the record.
    """

    record_type: str
    unique_id: int | str
    unique_field: str

    def __init__(
        self,
        record_type: type[Base],
        unique_id: int | str,
        unique_field: str = "id",
    ) -> None:
        """Initialize the exception with the given record type, unique record ID."""
        self.record_type = record_type.__name__
        self.unique_id = unique_id
        self.unique_field = unique_field
        super().__init__(f"{record_type} not found for {unique_field}={unique_id}.")


class ForbiddenError(Exception):
    """Exception raised when a user tries to access something without the proper permissions.

    This exception should only be thrown when the permissions service determines the user does not have the proper access for the requested action.
    """

    action: str

    unique_field: str

    def __init__(
        self,
        action: Literal["view", "edit", "create", "delete"],
        resource: str,
    ) -> None:
        """Initialize the exception with the given resource name and action they do not have permission for."""
        self.resource = resource

        super().__init__(f"User does not have permission to {action} {resource}.")


class DuplicateError(Exception):
    """Exception raised when user tries to create something that already exists."""

    resource: str

    def __init__(self, resource: str) -> None:
        """Initialize the exception."""
        super().__init__(f"Error, {resource} already exists.")
