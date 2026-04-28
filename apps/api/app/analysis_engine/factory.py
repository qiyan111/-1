from __future__ import annotations

from pathlib import Path

from app.analysis_engine.exceptions import UnsupportedFileTypeError
from app.analysis_engine.parsers import BaseFileParser, CsvFileParser, FcsFileParser, LmdFileParser


PARSER_BY_EXTENSION: dict[str, type[BaseFileParser]] = {
    ".csv": CsvFileParser,
    ".fcs": FcsFileParser,
    ".lmd": LmdFileParser,
}


def get_parser(file_path: str | Path) -> BaseFileParser:
    extension = Path(file_path).suffix.lower()
    parser_class = PARSER_BY_EXTENSION.get(extension)
    if parser_class is None:
        raise UnsupportedFileTypeError(f"Unsupported file type: {extension or '<none>'}")
    return parser_class()
