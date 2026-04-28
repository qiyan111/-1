from app.analysis_engine.statistics import build_immunophenotype_description, evaluate_statistics


EVENTS = [
    [10.0, 5.0, 100.0, 20.0],
    [20.0, 10.0, 200.0, 40.0],
    [30.0, 20.0, 300.0, 80.0],
    [40.0, 30.0, 400.0, 120.0],
]
CHANNELS = ["FSC-A", "SSC-A", "CD4", "CD8"]
GATE_MASKS = {
    "TOTAL": [True, True, True, True],
    "LYM": [True, True, True, False],
    "CD4": [False, True, True, False],
    "CD8": [True, False, False, True],
    "ABN": [False, True, True, False],
}
THRESHOLDS = [
    {"marker": "CD4", "channel": "CD4", "threshold_type": "positive", "threshold_value": 150.0},
    {"marker": "CD8", "channel": "CD8", "threshold_type": "negative", "threshold_value": 50.0},
    {"marker": "CD4", "channel": "CD4", "threshold_type": "high", "threshold_value": 250.0},
]


def result_by_name(definitions: list[dict]) -> dict[str, object]:
    results = evaluate_statistics(EVENTS, CHANNELS, GATE_MASKS, definitions, THRESHOLDS)
    return {result.name: result for result in results}


def test_percent_total() -> None:
    results = result_by_name([
        {"name": "LYM % total", "type": "percent_total", "gate": "LYM"},
    ])

    assert results["LYM % total"].value == 75.0
    assert results["LYM % total"].unit == "percent"


def test_percent_parent() -> None:
    results = result_by_name([
        {"name": "CD4 % LYM", "type": "percent_parent", "gate": "CD4", "parent_gate": "LYM"},
    ])

    assert results["CD4 % LYM"].value == (2 / 3) * 100.0


def test_ratio() -> None:
    results = result_by_name([
        {"name": "CD4/CD8", "type": "ratio", "numerator_gate": "CD4", "denominator_gate": "CD8"},
    ])

    assert results["CD4/CD8"].value == 1.0


def test_sum_of_gates() -> None:
    results = result_by_name([
        {"name": "CD4 + CD8", "type": "sum_of_gates", "gates": ["CD4", "CD8"]},
    ])

    assert results["CD4 + CD8"].value == 4
    assert results["CD4 + CD8"].unit == "events"


def test_marker_positive_and_negative() -> None:
    results = result_by_name([
        {"name": "CD4 positive", "type": "marker_positive", "gate": "LYM", "marker": "CD4"},
        {"name": "CD8 negative", "type": "marker_negative", "gate": "LYM", "marker": "CD8"},
    ])

    assert results["CD4 positive"].value == (2 / 3) * 100.0
    assert results["CD4 positive"].metadata["event_count"] == 2
    assert results["CD8 negative"].value == (2 / 3) * 100.0
    assert results["CD8 negative"].metadata["status"] == "negative"


def test_mean_median_absolute_count_and_high_expression() -> None:
    results = result_by_name([
        {"name": "CD4 mean", "type": "mean", "gate": "LYM", "channel": "CD4"},
        {"name": "CD4 median", "type": "median", "gate": "LYM", "channel": "CD4"},
        {"name": "LYM abs", "type": "absolute_count", "gate": "LYM", "reference_count": 4000},
        {"name": "CD4 high", "type": "high_expression", "gate": "LYM", "marker": "CD4"},
    ])

    assert results["CD4 mean"].value == 200.0
    assert results["CD4 median"].value == 200.0
    assert results["LYM abs"].value == 3000.0
    assert results["CD4 high"].value == (1 / 3) * 100.0


def test_immunophenotype_description() -> None:
    description = build_immunophenotype_description(
        "ABN",
        {"CD34": "positive", "CD19": "negative", "CD117": "high", "CD45": "low"},
    )
    results = result_by_name([
        {
            "name": "ABN phenotype",
            "type": "immunophenotype_description",
            "gate": "ABN",
            "marker_results": {
                "CD34": "positive",
                "CD19": "negative",
                "CD117": "high",
                "CD45": "low",
            },
        },
    ])

    assert description == "异常细胞群 ABN；表达 CD34；不表达 CD19；CD117 高表达；CD45 低表达。"
    assert results["ABN phenotype"].value == description
