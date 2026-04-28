from app.analysis_engine.gating import apply_parent_mask, evaluate_gate, evaluate_logic_gate


CHANNELS = ["FSC-A", "SSC-A", "CD45"]
EVENTS = [
    [0.0, 0.0, 5.0],
    [1.0, 1.0, 10.0],
    [2.0, 2.0, 20.0],
    [3.0, 1.0, 30.0],
    [4.0, 4.0, 40.0],
]


def test_rectangle_gate() -> None:
    result = evaluate_gate(
        EVENTS,
        CHANNELS,
        {
            "type": "rectangle",
            "x_channel": "FSC-A",
            "y_channel": "SSC-A",
            "x_min": 1.0,
            "x_max": 3.0,
            "y_min": 1.0,
            "y_max": 2.0,
        },
    )

    assert result.mask == [False, True, True, True, False]
    assert result.event_count == 3


def test_polygon_gate() -> None:
    result = evaluate_gate(
        EVENTS,
        CHANNELS,
        {
            "type": "polygon",
            "x_channel": "FSC-A",
            "y_channel": "SSC-A",
            "points": [[0.0, 0.0], [3.0, 0.0], [3.0, 3.0], [0.0, 3.0]],
        },
    )

    assert result.mask == [True, True, True, True, False]
    assert result.event_count == 4


def test_ellipse_gate() -> None:
    result = evaluate_gate(
        EVENTS,
        CHANNELS,
        {
            "type": "ellipse",
            "x_channel": "FSC-A",
            "y_channel": "SSC-A",
            "center_x": 1.5,
            "center_y": 1.5,
            "radius_x": 0.8,
            "radius_y": 0.8,
        },
    )

    assert result.mask == [False, True, True, False, False]
    assert result.event_count == 2


def test_circle_gate() -> None:
    result = evaluate_gate(
        EVENTS,
        CHANNELS,
        {
            "type": "circle",
            "x_channel": "FSC-A",
            "y_channel": "SSC-A",
            "center_x": 2.0,
            "center_y": 2.0,
            "radius": 1.5,
        },
    )

    assert result.mask == [False, True, True, True, False]
    assert result.event_count == 3


def test_quadrant_gate() -> None:
    result = evaluate_gate(
        EVENTS,
        CHANNELS,
        {
            "type": "quadrant",
            "x_channel": "FSC-A",
            "y_channel": "SSC-A",
            "x_threshold": 2.0,
            "y_threshold": 1.5,
            "quadrant": "upper_right",
        },
    )

    assert result.mask == [False, False, True, False, True]
    assert result.event_count == 2


def test_rotated_quadrant_gate() -> None:
    events = [[0.0, 1.0], [1.0, 0.0], [-1.0, 0.0], [0.0, -1.0]]
    result = evaluate_gate(
        events,
        ["X", "Y"],
        {
            "type": "rotated_quadrant",
            "x_channel": "X",
            "y_channel": "Y",
            "x_threshold": 0.0,
            "y_threshold": 0.0,
            "angle_degrees": 45.0,
            "quadrant": "upper_right",
        },
    )

    assert result.mask == [True, False, False, False]
    assert result.event_count == 1


def test_linear_gate() -> None:
    result = evaluate_gate(
        EVENTS,
        CHANNELS,
        {
            "type": "linear",
            "channel": "CD45",
            "min": 10.0,
            "max": 30.0,
        },
    )

    assert result.mask == [False, True, True, True, False]
    assert result.event_count == 3


def test_parent_child_gate() -> None:
    parent = evaluate_gate(
        EVENTS,
        CHANNELS,
        {
            "type": "rectangle",
            "x_channel": "FSC-A",
            "y_channel": "SSC-A",
            "x_min": 0.0,
            "x_max": 3.0,
            "y_min": 0.0,
            "y_max": 3.0,
        },
    )
    child = evaluate_gate(
        EVENTS,
        CHANNELS,
        {
            "type": "linear",
            "channel": "CD45",
            "min": 20.0,
        },
        parent_mask=parent.mask,
    )

    assert parent.mask == [True, True, True, True, False]
    assert child.mask == [False, False, True, True, False]
    assert child.event_count == 2
    assert apply_parent_mask([True, True, True], [True, False, True]) == [True, False, True]


def test_logic_and_gate() -> None:
    result = evaluate_logic_gate(
        {"op": "AND", "left": "A", "right": "B"},
        {
            "A": [True, True, False, False],
            "B": [True, False, True, False],
        },
    )

    assert result.mask == [True, False, False, False]
    assert result.event_count == 1


def test_logic_or_gate() -> None:
    result = evaluate_logic_gate(
        {"op": "OR", "left": "A", "right": "B"},
        {
            "A": [True, True, False, False],
            "B": [True, False, True, False],
        },
    )

    assert result.mask == [True, True, True, False]
    assert result.event_count == 3


def test_logic_a_not_b_gate() -> None:
    result = evaluate_logic_gate(
        {"op": "A_NOT_B", "left": "A", "right": "B"},
        {
            "A": [True, True, False, False],
            "B": [True, False, True, False],
        },
    )

    assert result.mask == [False, True, False, False]
    assert result.event_count == 1


def test_nested_logic_not_gate() -> None:
    result = evaluate_logic_gate(
        {
            "op": "AND",
            "left": "A",
            "right": {"op": "NOT", "operand": "B"},
        },
        {
            "A": [True, True, False, False],
            "B": [True, False, True, False],
        },
    )

    assert result.mask == [False, True, False, False]
    assert result.event_count == 1
