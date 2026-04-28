from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from pathlib import Path

from app.analysis_engine.exceptions import ParserNotImplementedError
from app.analysis_engine.schemas import ChannelInfo, CompensationMatrix, ParsedFile, ParsedMetadata


class BaseFileParser(ABC):
    format_name: str

    @abstractmethod
    def parse_metadata(self, file_path: str | Path) -> ParsedMetadata:
        raise NotImplementedError

    @abstractmethod
    def parse_events(self, file_path: str | Path) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def parse_channels(self, file_path: str | Path) -> list[ChannelInfo]:
        raise NotImplementedError

    @abstractmethod
    def parse_compensation(self, file_path: str | Path) -> CompensationMatrix:
        raise NotImplementedError

    def parse(self, file_path: str | Path) -> ParsedFile:
        return ParsedFile(
            channels=self.parse_channels(file_path),
            events=self.parse_events(file_path),
            metadata=self.parse_metadata(file_path),
            compensation=self.parse_compensation(file_path),
        )


class CsvFileParser(BaseFileParser):
    format_name = "CSV"

    def parse_metadata(self, file_path: str | Path) -> ParsedMetadata:
        path = Path(file_path)
        rows, comments = self._read_rows(path)
        channel_names = self._channel_names(rows)
        return ParsedMetadata(
            format=self.format_name,
            file_name=path.name,
            row_count=max(len(rows) - 1, 0),
            channel_count=len(channel_names),
            attributes={
                "delimiter": ",",
                "comments": comments,
            },
        )

    def parse_events(self, file_path: str | Path) -> list[list[float]]:
        rows, _comments = self._read_rows(Path(file_path))
        self._channel_names(rows)
        events: list[list[float]] = []
        for row_number, row in enumerate(rows[1:], start=2):
            try:
                events.append([float(value) for value in row])
            except ValueError as exc:
                raise ValueError(f"CSV row {row_number} contains a non-numeric event value") from exc
        return events

    def parse_channels(self, file_path: str | Path) -> list[ChannelInfo]:
        rows, _comments = self._read_rows(Path(file_path))
        return [
            ChannelInfo(name=name, index=index)
            for index, name in enumerate(self._channel_names(rows))
        ]

    def parse_compensation(self, file_path: str | Path) -> CompensationMatrix:
        channel_names = [channel.name for channel in self.parse_channels(file_path)]
        size = len(channel_names)
        return CompensationMatrix(
            channel_names=channel_names,
            matrix=[
                [1.0 if row_index == column_index else 0.0 for column_index in range(size)]
                for row_index in range(size)
            ],
            source="identity",
        )

    def _read_rows(self, path: Path) -> tuple[list[list[str]], dict[str, str]]:
        comments: dict[str, str] = {}
        data_lines: list[str] = []
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            for line in file:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    key, separator, value = stripped[1:].partition(":")
                    if separator:
                        comments[key.strip()] = value.strip()
                    continue
                data_lines.append(line)

        rows = list(csv.reader(data_lines))
        if not rows:
            raise ValueError("CSV file has no header row")
        return rows, comments

    @staticmethod
    def _channel_names(rows: list[list[str]]) -> list[str]:
        channel_names = [name.strip() for name in rows[0]]
        if not channel_names or any(not name for name in channel_names):
            raise ValueError("CSV header contains an empty channel name")
        expected_width = len(channel_names)
        for row_number, row in enumerate(rows[1:], start=2):
            if len(row) != expected_width:
                raise ValueError(
                    f"CSV row {row_number} has {len(row)} values, expected {expected_width}"
                )
        return channel_names


class FcsFileParser(BaseFileParser):
    format_name = "FCS"

    def parse_metadata(self, file_path: str | Path) -> ParsedMetadata:
        raise ParserNotImplementedError("FCS parsing adapter is not implemented yet")

    def parse_events(self, file_path: str | Path) -> list[list[float]]:
        raise ParserNotImplementedError("FCS parsing adapter is not implemented yet")

    def parse_channels(self, file_path: str | Path) -> list[ChannelInfo]:
        raise ParserNotImplementedError("FCS parsing adapter is not implemented yet")

    def parse_compensation(self, file_path: str | Path) -> CompensationMatrix:
        raise ParserNotImplementedError("FCS parsing adapter is not implemented yet")


class LmdFileParser(BaseFileParser):
    format_name = "LMD"

    def parse_metadata(self, file_path: str | Path) -> ParsedMetadata:
        raise ParserNotImplementedError("LMD parsing adapter is not implemented yet")

    def parse_events(self, file_path: str | Path) -> list[list[float]]:
        raise ParserNotImplementedError("LMD parsing adapter is not implemented yet")

    def parse_channels(self, file_path: str | Path) -> list[ChannelInfo]:
        raise ParserNotImplementedError("LMD parsing adapter is not implemented yet")

    def parse_compensation(self, file_path: str | Path) -> CompensationMatrix:
        raise ParserNotImplementedError("LMD parsing adapter is not implemented yet")
