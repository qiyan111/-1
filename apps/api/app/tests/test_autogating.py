import pytest

from app.analysis_engine.autogating import (
    AutoQuadrantGate,
    DBSCANAutoGate,
    DensityValleyThresholdGate,
    KMeansAutoGate,
    WardAutoGate,
)


def two_cluster_events() -> list[list[float]]:
    return [
        [0.0, 0.1],
        [0.2, -0.1],
        [-0.2, 0.0],
        [5.0, 5.1],
        [5.2, 4.9],
        [4.8, 5.0],
    ]


def density_events() -> list[list[float]]:
    return [[value] for value in [1.0, 1.0, 1.1, 1.2, 8.8, 9.0, 9.1, 9.2]]


def quadrant_events() -> list[list[float]]:
    return [
        [-2.0, -2.0],
        [-1.0, 2.0],
        [2.0, -1.0],
        [3.0, 3.0],
    ]


def assert_common_outputs(algorithm, expected_type: str) -> None:
    gate = algorithm.predict_gate()
    confidence = algorithm.confidence()
    metadata = algorithm.metadata()

    assert gate["type"] == expected_type
    assert confidence.level in {"green", "yellow", "red"}
    assert 0.0 <= confidence.score <= 1.0
    assert confidence.reasons
    assert metadata["algorithm_name"]
    assert metadata["algorithm_version"] == "1.0"
    assert metadata["runtime_ms"] >= 0.0
    assert isinstance(metadata["parameters"], dict)


def test_kmeans_auto_gate_outputs_ellipse_and_confidence() -> None:
    algorithm = KMeansAutoGate().fit(
        two_cluster_events(),
        ["FSC-A", "SSC-A"],
        {"x_channel": "FSC-A", "y_channel": "SSC-A", "k": 2, "target_cluster": "largest"},
    )

    gate = algorithm.predict_gate()
    assert_common_outputs(algorithm, "ellipse")
    assert gate["x_channel"] == "FSC-A"
    assert gate["y_channel"] == "SSC-A"
    assert "center_x" in gate
    assert "radius_x" in gate


def test_dbscan_auto_gate_outputs_rectangle() -> None:
    algorithm = DBSCANAutoGate().fit(
        two_cluster_events(),
        ["FSC-A", "SSC-A"],
        {"x_channel": "FSC-A", "y_channel": "SSC-A", "eps": 0.5, "min_samples": 2},
    )

    gate = algorithm.predict_gate()
    assert_common_outputs(algorithm, "rectangle")
    assert gate["x_min"] <= gate["x_max"]
    assert gate["y_min"] <= gate["y_max"]


def test_ward_auto_gate_outputs_ellipse() -> None:
    algorithm = WardAutoGate().fit(
        two_cluster_events(),
        ["FSC-A", "SSC-A"],
        {"x_channel": "FSC-A", "y_channel": "SSC-A", "n_clusters": 2},
    )

    gate = algorithm.predict_gate()
    assert_common_outputs(algorithm, "ellipse")
    assert gate["center_x"] >= -0.2
    assert gate["center_y"] >= -0.1


def test_density_valley_threshold_gate_outputs_linear_gate() -> None:
    algorithm = DensityValleyThresholdGate().fit(
        density_events(),
        ["CD45"],
        {"channel": "CD45", "bins": 8, "direction": "above"},
    )

    gate = algorithm.predict_gate()
    assert_common_outputs(algorithm, "linear")
    assert gate["channel"] == "CD45"
    assert 1.2 < gate["min"] < 8.8


def test_auto_quadrant_gate_outputs_quadrant_gate() -> None:
    algorithm = AutoQuadrantGate().fit(
        quadrant_events(),
        ["CD4", "CD8"],
        {"x_channel": "CD4", "y_channel": "CD8", "quadrant": "upper_right"},
    )

    gate = algorithm.predict_gate()
    assert_common_outputs(algorithm, "quadrant")
    assert gate["x_channel"] == "CD4"
    assert gate["y_channel"] == "CD8"
    assert gate["quadrant"] == "upper_right"


def test_parameter_errors_are_reported() -> None:
    with pytest.raises(ValueError, match="x_channel and y_channel"):
        KMeansAutoGate().fit(two_cluster_events(), ["FSC-A", "SSC-A"], {"x_channel": "FSC-A"})

    with pytest.raises(ValueError, match="eps must be positive"):
        DBSCANAutoGate().fit(
            two_cluster_events(),
            ["FSC-A", "SSC-A"],
            {"x_channel": "FSC-A", "y_channel": "SSC-A", "eps": 0},
        )

    with pytest.raises(ValueError, match="bins must be at least 3"):
        DensityValleyThresholdGate().fit(density_events(), ["CD45"], {"channel": "CD45", "bins": 2})


def test_predict_gate_requires_fit() -> None:
    with pytest.raises(ValueError, match="must be fitted"):
        KMeansAutoGate().predict_gate()
