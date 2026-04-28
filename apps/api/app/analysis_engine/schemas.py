from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChannelInfo:
    name: str
    index: int
    data_type: str = "float"
    detector: str | None = None
    marker: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedMetadata:
    format: str
    file_name: str
    row_count: int
    channel_count: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompensationMatrix:
    channel_names: list[str]
    matrix: list[list[float]]
    source: str = "identity"


@dataclass(frozen=True)
class ParsedFile:
    channels: list[ChannelInfo]
    events: list[list[float]]
    metadata: ParsedMetadata
    compensation: CompensationMatrix
