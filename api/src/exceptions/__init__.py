"""Exceptions."""


class TerriscopeException(Exception):
    """TerriscopeException."""

    def __init__(self, code: int, msg: str):
        """Initialize generic terriscope exception."""
        super().__init__(f"Exception {code}: {msg}")
        self.code = code
        self.msg = msg
