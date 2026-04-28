from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


EventMatrix = list[list[float]]
BooleanMask = list[bool]
GateDefinition = dict[str, Any]


@dataclass(frozen=True)
class GateEvaluation:
    mask: BooleanMask
    event_count: int


def evaluate_gate(
    events: EventMatrix,
    channel_names: list[str],
    gate_definition: GateDefinition,
    parent_mask: BooleanMask | None = None,
) -> GateEvaluation:
    gate_type = str(gate_definition.get("type", "")).lower()
    if gate_type == "rectangle":
        mask = _rectangle_mask(events, channel_names, gate_definition)
    elif gate_type == "polygon":
        mask = _polygon_mask(events, channel_names, gate_definition)
    elif gate_type == "ellipse":
        mask = _ellipse_mask(events, channel_names, gate_definition)
    elif gate_type == "circle":
        mask = _circle_mask(events, channel_names, gate_definition)
    elif gate_type == "quadrant":
        mask = _quadrant_mask(events, channel_names, gate_definition, angle_degrees=0.0)
    elif gate_type == "rotated_quadrant":
        mask = _quadrant_mask(
            events,
            channel_names,
            gate_definition,
            angle_degrees=float(gate_definition.get("angle_degrees", 0.0)),
        )
    elif gate_type == "linear":
        mask = _linear_mask(events, channel_names, gate_definition)
    else:
        raise ValueError(f"Unsupported gate type: {gate_type or '<missing>'}")

    mask = apply_parent_mask(mask, parent_mask)
    return GateEvaluation(mask=mask, event_count=sum(mask))


def apply_parent_mask(mask: BooleanMask, parent_mask: BooleanMask | None) -> BooleanMask:
    if parent_mask is None:
        return mask
    if len(mask) != len(parent_mask):
        raise ValueError("Parent mask length must match current mask length")
    return [parent_selected and selected for parent_selected, selected in zip(parent_mask, mask)]


def evaluate_logic_gate(expression: dict[str, Any] | str, masks: dict[str, BooleanMask]) -> GateEvaluation:
    mask = _evaluate_logic_expression(expression, masks)
    return GateEvaluation(mask=mask, event_count=sum(mask))


def _rectangle_mask(events: EventMatrix, channel_names: list[str], definition: GateDefinition) -> BooleanMask:
    x_index = _channel_index(channel_names, definition["x_channel"])
    y_index = _channel_index(channel_names, definition["y_channel"])
    x_min = float(definition["x_min"])
    x_max = float(definition["x_max"])
    y_min = float(definition["y_min"])
    y_max = float(definition["y_max"])
    return [
        x_min <= event[x_index] <= x_max and y_min <= event[y_index] <= y_max
        for event in events
    ]


def _polygon_mask(events: EventMatrix, channel_names: list[str], definition: GateDefinition) -> BooleanMask:
    x_index = _channel_index(channel_names, definition["x_channel"])
    y_index = _channel_index(channel_names, definition["y_channel"])
    points = [(float(x), float(y)) for x, y in definition["points"]]
    if len(points) < 3:
        raise ValueError("Polygon gate requires at least three points")
    return [_point_in_polygon(event[x_index], event[y_index], points) for event in events]


def _ellipse_mask(events: EventMatrix, channel_names: list[str], definition: GateDefinition) -> BooleanMask:
    x_index = _channel_index(channel_names, definition["x_channel"])
    y_index = _channel_index(channel_names, definition["y_channel"])
    center_x = float(definition["center_x"])
    center_y = float(definition["center_y"])
    radius_x = float(definition["radius_x"])
    radius_y = float(definition["radius_y"])
    angle = math.radians(float(definition.get("angle_degrees", 0.0)))
    if radius_x <= 0 or radius_y <= 0:
        raise ValueError("Ellipse radii must be positive")
    return [
        (_rotate_x(event[x_index] - center_x, event[y_index] - center_y, -angle) / radius_x) ** 2
        + (_rotate_y(event[x_index] - center_x, event[y_index] - center_y, -angle) / radius_y) ** 2
        <= 1.0
        for event in events
    ]


def _circle_mask(events: EventMatrix, channel_names: list[str], definition: GateDefinition) -> BooleanMask:
    circle_definition = {
        **definition,
        "radius_x": definition["radius"],
        "radius_y": definition["radius"],
        "angle_degrees": 0.0,
    }
    return _ellipse_mask(events, channel_names, circle_definition)


def _quadrant_mask(
    events: EventMatrix,
    channel_names: list[str],
    definition: GateDefinition,
    *,
    angle_degrees: float,
) -> BooleanMask:
    x_index = _channel_index(channel_names, definition["x_channel"])
    y_index = _channel_index(channel_names, definition["y_channel"])
    center_x = float(definition["x_threshold"])
    center_y = float(definition["y_threshold"])
    quadrant = str(definition["quadrant"]).lower()
    angle = math.radians(angle_degrees)
    mask: BooleanMask = []
    for event in events:
        shifted_x = event[x_index] - center_x
        shifted_y = event[y_index] - center_y
        rotated_x = _rotate_x(shifted_x, shifted_y, -angle)
        rotated_y = _rotate_y(shifted_x, shifted_y, -angle)
        mask.append(_in_quadrant(rotated_x, rotated_y, quadrant))
    return mask


def _linear_mask(events: EventMatrix, channel_names: list[str], definition: GateDefinition) -> BooleanMask:
    channel_index = _channel_index(channel_names, definition["channel"])
    lower = definition.get("min")
    upper = definition.get("max")
    if lower is None and upper is None:
        raise ValueError("Linear gate requires min or max")
    lower_value = float(lower) if lower is not None else -math.inf
    upper_value = float(upper) if upper is not None else math.inf
    return [lower_value <= event[channel_index] <= upper_value for event in events]


def _evaluate_logic_expression(expression: dict[str, Any] | str, masks: dict[str, BooleanMask]) -> BooleanMask:
    if isinstance(expression, str):
        return list(_mask_by_name(expression, masks))

    operator = str(expression["op"]).upper()
    if operator == "NOT":
        operand = _evaluate_logic_expression(expression["operand"], masks)
        return [not value for value in operand]

    left = _evaluate_logic_expression(expression["left"], masks)
    right = _evaluate_logic_expression(expression["right"], masks)
    _ensure_same_length(left, right)
    if operator == "AND":
        return [left_value and right_value for left_value, right_value in zip(left, right)]
    if operator == "OR":
        return [left_value or right_value for left_value, right_value in zip(left, right)]
    if operator in {"A_NOT_B", "AND_NOT"}:
        return [left_value and not right_value for left_value, right_value in zip(left, right)]
    raise ValueError(f"Unsupported logic operator: {operator}")


def _mask_by_name(name: str, masks: dict[str, BooleanMask]) -> BooleanMask:
    try:
        return masks[name]
    except KeyError as exc:
        raise ValueError(f"Unknown gate mask: {name}") from exc


def _ensure_same_length(left: BooleanMask, right: BooleanMask) -> None:
    if len(left) != len(right):
        raise ValueError("Logic gate masks must have the same length")


def _channel_index(channel_names: list[str], channel_name: str) -> int:
    try:
        return channel_names.index(channel_name)
    except ValueError as exc:
        raise ValueError(f"Unknown channel: {channel_name}") from exc


def _point_in_polygon(x: float, y: float, points: list[tuple[float, float]]) -> bool:
    inside = False
    previous_x, previous_y = points[-1]
    for current_x, current_y in points:
        if _point_on_segment(x, y, previous_x, previous_y, current_x, current_y):
            return True
        crosses_y = (current_y > y) != (previous_y > y)
        if crosses_y:
            intersection_x = (
                (previous_x - current_x) * (y - current_y) / (previous_y - current_y)
                + current_x
            )
            if x <= intersection_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _point_on_segment(
    x: float,
    y: float,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> bool:
    cross_product = (y - start_y) * (end_x - start_x) - (x - start_x) * (end_y - start_y)
    if abs(cross_product) > 1e-9:
        return False
    return (
        min(start_x, end_x) - 1e-9 <= x <= max(start_x, end_x) + 1e-9
        and min(start_y, end_y) - 1e-9 <= y <= max(start_y, end_y) + 1e-9
    )


def _rotate_x(x: float, y: float, angle: float) -> float:
    return x * math.cos(angle) - y * math.sin(angle)


def _rotate_y(x: float, y: float, angle: float) -> float:
    return x * math.sin(angle) + y * math.cos(angle)


def _in_quadrant(x: float, y: float, quadrant: str) -> bool:
    if quadrant in {"upper_right", "ur", "q1"}:
        return x >= 0 and y >= 0
    if quadrant in {"upper_left", "ul", "q2"}:
        return x < 0 and y >= 0
    if quadrant in {"lower_left", "ll", "q3"}:
        return x < 0 and y < 0
    if quadrant in {"lower_right", "lr", "q4"}:
        return x >= 0 and y < 0
    raise ValueError(f"Unsupported quadrant: {quadrant}")
