class NotFoundError(Exception):
    """The resource doesn't exist or belongs to another user. The API returns 404."""


class ConflictError(Exception):
    """The request clashes with existing data (e.g. a duplicate name). The API returns 409."""
