from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any


EventMatrix = list[list[float]]
BooleanMask = list[bool]
StatisticDefinition = dict[str, Any]
MarkerThreshold = dict[str, Any]


@dataclass(frozen=True)
class StatisticResult:
    name: str
    statistic_type: str
    value: float | int | str | None
    unit: str | None = None
    metadata: dict[str, Any] | None = None


def evaluate_statistics(
    events: EventMatrix,
    channels: list[str],
    gate_masks: dict[str, BooleanMask],
    statistics_definitions: list[StatisticDefinition],
    marker_thresholds: list[MarkerThreshold] | None = None,
) -> list[StatisticResult]:
    thresholds = marker_thresholds or []
    return [
        _evaluate_statistic(events, channels, gate_masks, definition, thresholds)
        for definition in statistics_definitions
    ]


def build_immunophenotype_description(
    gate_name: str,
    marker_results: dict[str, str],
    *,
    prefix: str = "异常细胞群",
) -> str:
    positive_markers = sorted(marker for marker, status in marker_results.items() if status == "positive")
    negative_markers = sorted(marker for marker, status in marker_results.items() if status == "negative")
    high_markers = sorted(marker for marker, status in marker_results.items() if status == "high")
    low_markers = sorted(marker for marker, status in marker_results.items() if status == "low")

    parts: list[str] = [f"{prefix} {gate_name}"]
    if positive_markers:
        parts.append(f"表达 {', '.join(positive_markers)}")
    if negative_markers:
        parts.append(f"不表达 {', '.join(negative_markers)}")
    if high_markers:
        parts.append(f"{', '.join(high_markers)} 高表达")
    if low_markers:
        parts.append(f"{', '.join(low_markers)} 低表达")
    return "；".join(parts) + "。"


def _evaluate_statistic(
    events: EventMatrix,
    channels: list[str],
    gate_masks: dict[str, BooleanMask],
    definition: StatisticDefinition,
    marker_thresholds: list[MarkerThreshold],
) -> StatisticResult:
    statistic_type = str(definition["type"]).lower()
    name = str(definition.get("name") or statistic_type)

    if statistic_type == "event_count":
        gate = str(definition["gate"])
        value = _count(_mask(gate_masks, gate))
        return StatisticResult(name=name, statistic_type=statistic_type, value=value, unit="events")

    if statistic_type == "percent_total":
        gate = str(definition["gate"])
        value = _safe_percent(_count(_mask(gate_masks, gate)), len(events))
        return StatisticResult(name=name, statistic_type=statistic_type, value=value, unit="percent")

    if statistic_type == "percent_parent":
        gate = str(definition["gate"])
        parent_gate = str(definition["parent_gate"])
        value = _safe_percent(_count(_mask(gate_masks, gate)), _count(_mask(gate_masks, parent_gate)))
        return StatisticResult(name=name, statistic_type=statistic_type, value=value, unit="percent")

    if statistic_type == "percent_of_gate":
        gate = str(definition["gate"])
        denominator_gate = str(definition["denominator_gate"])
        value = _safe_percent(_count(_mask(gate_masks, gate)), _count(_mask(gate_masks, denominator_gate)))
        return StatisticResult(name=name, statistic_type=statistic_type, value=value, unit="percent")

    if statistic_type in {"mean", "median"}:
        gate = str(definition["gate"])
        channel = str(definition["channel"])
        values = _selected_channel_values(events, channels, _mask(gate_masks, gate), channel)
        if not values:
            value = None
        elif statistic_type == "mean":
            value = statistics.fmean(values)
        else:
            value = float(statistics.median(values))
        return StatisticResult(
            name=name,
            statistic_type=statistic_type,
            value=value,
            metadata={"gate": gate, "channel": channel},
        )

    if statistic_type == "ratio":
        numerator_gate = str(definition["numerator_gate"])
        denominator_gate = str(definition["denominator_gate"])
        denominator = _count(_mask(gate_masks, denominator_gate))
        value = None if denominator == 0 else _count(_mask(gate_masks, numerator_gate)) / denominator
        return StatisticResult(
            name=name,
            statistic_type=statistic_type,
            value=value,
            metadata={"numerator_gate": numerator_gate, "denominator_gate": denominator_gate},
        )

    if statistic_type == "sum_of_gates":
        gates = [str(gate) for gate in definition["gates"]]
        value = sum(_count(_mask(gate_masks, gate)) for gate in gates)
        return StatisticResult(name=name, statistic_type=statistic_type, value=value, unit="events", metadata={"gates": gates})

    if statistic_type == "absolute_count":
        gate = str(definition["gate"])
        reference_count = float(definition["reference_count"])
        denominator_gate = definition.get("denominator_gate")
        denominator = _count(_mask(gate_masks, str(denominator_gate))) if denominator_gate else len(events)
        value = reference_count * (_count(_mask(gate_masks, gate)) / denominator) if denominator else None
        return StatisticResult(
            name=name,
            statistic_type=statistic_type,
            value=value,
            unit=str(definition.get("unit") or "cells/uL"),
        )

    if statistic_type in {"marker_positive", "marker_negative", "high_expression", "low_expression"}:
        return _evaluate_marker_statistic(events, channels, gate_masks, definition, marker_thresholds, name, statistic_type)

    if statistic_type == "immunophenotype_description":
        gate = str(definition["gate"])
        marker_results = {
            str(marker): str(status)
            for marker, status in definition.get("marker_results", {}).items()
        }
        value = build_immunophenotype_description(
            gate,
            marker_results,
            prefix=str(definition.get("prefix") or "异常细胞群"),
        )
        return StatisticResult(name=name, statistic_type=statistic_type, value=value, metadata={"gate": gate})

    raise ValueError(f"Unsupported statistic type: {statistic_type}")


def _evaluate_marker_statistic(
    events: EventMatrix,
    channels: list[str],
    gate_masks: dict[str, BooleanMask],
    definition: StatisticDefinition,
    marker_thresholds: list[MarkerThreshold],
    name: str,
    statistic_type: str,
) -> StatisticResult:
    gate = str(definition["gate"])
    marker = str(definition["marker"])
    threshold = _find_threshold(marker_thresholds, marker, statistic_type, definition)
    channel = str(definition.get("channel") or threshold["channel"])
    threshold_value = float(definition.get("threshold_value", threshold["threshold_value"]))
    values = _selected_channel_values(events, channels, _mask(gate_masks, gate), channel)

    if statistic_type == "marker_positive":
        selected = [value for value in values if value >= threshold_value]
        status = "positive"
    elif statistic_type == "marker_negative":
        selected = [value for value in values if value < threshold_value]
        status = "negative"
    elif statistic_type == "high_expression":
        selected = [value for value in values if value >= threshold_value]
        status = "high"
    else:
        selected = [value for value in values if value < threshold_value]
        status = "low"

    value = _safe_percent(len(selected), len(values))
    return StatisticResult(
        name=name,
        statistic_type=statistic_type,
        value=value,
        unit="percent",
        metadata={
            "gate": gate,
            "marker": marker,
            "channel": channel,
            "threshold_value": threshold_value,
            "status": status,
            "event_count": len(selected),
            "gate_event_count": len(values),
        },
    )


def _find_threshold(
    marker_thresholds: list[MarkerThreshold],
    marker: str,
    statistic_type: str,
    definition: StatisticDefinition,
) -> MarkerThreshold:
    if "threshold_value" in definition and "channel" in definition:
        return {
            "marker": marker,
            "channel": definition["channel"],
            "threshold_value": definition["threshold_value"],
            "threshold_type": statistic_type,
        }

    aliases = {
        "marker_positive": {"positive", "marker_positive"},
        "marker_negative": {"negative", "marker_negative"},
        "high_expression": {"high", "high_expression"},
        "low_expression": {"low", "low_expression"},
    }
    expected_types = aliases[statistic_type]
    for threshold in marker_thresholds:
        if str(threshold.get("marker")) == marker and str(threshold.get("threshold_type", "")).lower() in expected_types:
            return threshold
    raise ValueError(f"Missing marker threshold for {marker} / {statistic_type}")


def _selected_channel_values(
    events: EventMatrix,
    channels: list[str],
    mask: BooleanMask,
    channel: str,
) -> list[float]:
    if len(mask) != len(events):
        raise ValueError("Gate mask length must match event count")
    channel_index = _channel_index(channels, channel)
    return [event[channel_index] for event, selected in zip(events, mask) if selected]


def _mask(gate_masks: dict[str, BooleanMask], gate: str) -> BooleanMask:
    try:
        return gate_masks[gate]
    except KeyError as exc:
        raise ValueError(f"Unknown gate mask: {gate}") from exc


def _count(mask: BooleanMask) -> int:
    return sum(mask)


def _safe_percent(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return (numerator / denominator) * 100.0


def _channel_index(channels: list[str], channel: str) -> int:
    try:
        return channels.index(channel)
    except ValueError as exc:
        raise ValueError(f"Unknown channel: {channel}") from exc
