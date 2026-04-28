from __future__ import annotations


class ParserError(Exception):
    """Base exception for file parser failures."""


class UnsupportedFileTypeError(ParserError):
    """Raised when no parser exists for a file extension."""


class ParserNotImplementedError(ParserError, NotImplementedError):
    """Raised by adapter shells that are intentionally not implemented yet."""
