from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


EventMatrix = list[list[float]]
GateDefinition = dict[str, Any]


@dataclass(frozen=True)
class ConfidenceScore:
    level: str
    score: float
    reasons: list[str] = field(default_factory=list)


class AutoGateAlgorithm:
    algorithm_name = "base"
    algorithm_version = "1.0"

    def __init__(self) -> None:
        self._events: EventMatrix | None = None
        self._channels: list[str] | None = None
        self._params: dict[str, Any] = {}
        self._gate_definition: GateDefinition | None = None
        self._confidence = ConfidenceScore(level="red", score=0.0, reasons=["Algorithm has not been fitted"])
        self._runtime_ms = 0.0

    def fit(
        self,
        events: EventMatrix,
        channels: list[str],
        params: dict[str, Any] | None = None,
    ) -> AutoGateAlgorithm:
        start = time.perf_counter()
        self._validate_events(events, channels)
        self._events = events
        self._channels = channels
        self._params = params or {}
        self._fit(events, channels, self._params)
        self._runtime_ms = (time.perf_counter() - start) * 1000.0
        return self

    def predict_gate(self) -> GateDefinition:
        if self._gate_definition is None:
            raise ValueError("Algorithm must be fitted before predict_gate")
        return self._gate_definition

    def confidence(self) -> ConfidenceScore:
        return self._confidence

    def metadata(self) -> dict[str, Any]:
        return {
            "algorithm_name": self.algorithm_name,
            "algorithm_version": self.algorithm_version,
            "parameters": self._params,
            "runtime_ms": self._runtime_ms,
        }

    def _fit(self, events: EventMatrix, channels: list[str], params: dict[str, Any]) -> None:
        raise NotImplementedError

    @staticmethod
    def _validate_events(events: EventMatrix, channels: list[str]) -> None:
        if not events:
            raise ValueError("events must not be empty")
        if not channels:
            raise ValueError("channels must not be empty")
        width = len(channels)
        for index, event in enumerate(events):
            if len(event) != width:
                raise ValueError(f"event {index} width does not match channel count")
