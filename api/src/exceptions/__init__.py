"""Exceptions."""


class TerramapsException(Exception):
    """TerramapsException."""

    def __init__(self, code: int, msg: str):
        """Initialize generic terramaps exception."""
        super().__init__(f"Exception {code}: {msg}")
        self.code = code
        self.msg = msg
