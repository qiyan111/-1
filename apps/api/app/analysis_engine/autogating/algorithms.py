from __future__ import annotations

import math
from typing import Any

from app.analysis_engine.autogating.base import AutoGateAlgorithm, ConfidenceScore, EventMatrix


class KMeansAutoGate(AutoGateAlgorithm):
    algorithm_name = "kmeans"

    def _fit(self, events: EventMatrix, channels: list[str], params: dict[str, Any]) -> None:
        x_channel, y_channel = _xy_channels(params)
        k = int(params.get("k", 2))
        if k < 2:
            raise ValueError("k must be at least 2")
        points = _points(events, channels, x_channel, y_channel)
        labels, centroids = _kmeans(points, k=k, max_iter=int(params.get("max_iter", 50)))
        target_label = _select_cluster(labels, mode=str(params.get("target_cluster", "largest")))
        selected = [point for point, label in zip(points, labels) if label == target_label]
        self._gate_definition = _ellipse_gate_from_points(
            selected,
            x_channel,
            y_channel,
            scale=float(params.get("scale", 2.0)),
            gate_name=str(params.get("gate_name", "KMeans Auto Gate")),
        )
        self._confidence = _cluster_confidence(points, labels, target_label, centroids[target_label])


class DBSCANAutoGate(AutoGateAlgorithm):
    algorithm_name = "dbscan"

    def _fit(self, events: EventMatrix, channels: list[str], params: dict[str, Any]) -> None:
        x_channel, y_channel = _xy_channels(params)
        eps = float(params.get("eps", 1.0))
        min_samples = int(params.get("min_samples", 3))
        if eps <= 0:
            raise ValueError("eps must be positive")
        if min_samples < 1:
            raise ValueError("min_samples must be at least 1")
        points = _points(events, channels, x_channel, y_channel)
        labels = _dbscan(points, eps=eps, min_samples=min_samples)
        clusters = [label for label in set(labels) if label >= 0]
        if not clusters:
            raise ValueError("DBSCAN found no clusters")
        target_label = max(clusters, key=lambda label: labels.count(label))
        selected = [point for point, label in zip(points, labels) if label == target_label]
        self._gate_definition = _rectangle_gate_from_points(
            selected,
            x_channel,
            y_channel,
            padding=float(params.get("padding", 0.0)),
            gate_name=str(params.get("gate_name", "DBSCAN Auto Gate")),
        )
        noise_fraction = labels.count(-1) / len(labels)
        score = max(0.0, min(1.0, (len(selected) / len(points)) * (1.0 - noise_fraction)))
        self._confidence = _confidence_from_score(score, [f"noise_fraction={noise_fraction:.3f}"])


class WardAutoGate(AutoGateAlgorithm):
    algorithm_name = "ward"

    def _fit(self, events: EventMatrix, channels: list[str], params: dict[str, Any]) -> None:
        x_channel, y_channel = _xy_channels(params)
        n_clusters = int(params.get("n_clusters", 2))
        if n_clusters < 2:
            raise ValueError("n_clusters must be at least 2")
        points = _points(events, channels, x_channel, y_channel)
        labels, centroids = _agglomerative_centroid(points, n_clusters=n_clusters)
        target_label = _select_cluster(labels, mode=str(params.get("target_cluster", "largest")))
        selected = [point for point, label in zip(points, labels) if label == target_label]
        self._gate_definition = _ellipse_gate_from_points(
            selected,
            x_channel,
            y_channel,
            scale=float(params.get("scale", 2.0)),
            gate_name=str(params.get("gate_name", "Ward Auto Gate")),
        )
        self._confidence = _cluster_confidence(points, labels, target_label, centroids[target_label])


class DensityValleyThresholdGate(AutoGateAlgorithm):
    algorithm_name = "density_valley_threshold"

    def _fit(self, events: EventMatrix, channels: list[str], params: dict[str, Any]) -> None:
        channel = str(params.get("channel", ""))
        if not channel:
            raise ValueError("channel is required")
        channel_index = _channel_index(channels, channel)
        values = sorted(event[channel_index] for event in events)
        bins = int(params.get("bins", 16))
        if bins < 3:
            raise ValueError("bins must be at least 3")
        threshold, separation = _density_valley(values, bins)
        direction = str(params.get("direction", "above")).lower()
        if direction == "above":
            gate = {"type": "linear", "channel": channel, "min": threshold}
        elif direction == "below":
            gate = {"type": "linear", "channel": channel, "max": threshold}
        else:
            raise ValueError("direction must be 'above' or 'below'")
        self._gate_definition = {**gate, "name": str(params.get("gate_name", "Density Valley Auto Gate"))}
        self._confidence = _confidence_from_score(
            max(0.0, min(1.0, separation)),
            [f"threshold={threshold:.6g}", f"separation={separation:.3f}"],
        )


class AutoQuadrantGate(AutoGateAlgorithm):
    algorithm_name = "auto_quadrant"

    def _fit(self, events: EventMatrix, channels: list[str], params: dict[str, Any]) -> None:
        x_channel, y_channel = _xy_channels(params)
        x_values = [event[_channel_index(channels, x_channel)] for event in events]
        y_values = [event[_channel_index(channels, y_channel)] for event in events]
        x_threshold = float(params.get("x_threshold", _median(x_values)))
        y_threshold = float(params.get("y_threshold", _median(y_values)))
        quadrant = str(params.get("quadrant", "upper_right"))
        self._gate_definition = {
            "type": "quadrant",
            "name": str(params.get("gate_name", "Auto Quadrant Gate")),
            "x_channel": x_channel,
            "y_channel": y_channel,
            "x_threshold": x_threshold,
            "y_threshold": y_threshold,
            "quadrant": quadrant,
        }
        x_balance = _side_balance(x_values, x_threshold)
        y_balance = _side_balance(y_values, y_threshold)
        score = 1.0 - ((x_balance + y_balance) / 2.0)
        self._confidence = _confidence_from_score(score, [f"x_threshold={x_threshold:.6g}", f"y_threshold={y_threshold:.6g}"])


def _xy_channels(params: dict[str, Any]) -> tuple[str, str]:
    x_channel = str(params.get("x_channel", ""))
    y_channel = str(params.get("y_channel", ""))
    if not x_channel or not y_channel:
        raise ValueError("x_channel and y_channel are required")
    return x_channel, y_channel


def _channel_index(channels: list[str], channel: str) -> int:
    try:
        return channels.index(channel)
    except ValueError as exc:
        raise ValueError(f"Unknown channel: {channel}") from exc


def _points(events: EventMatrix, channels: list[str], x_channel: str, y_channel: str) -> list[tuple[float, float]]:
    x_index = _channel_index(channels, x_channel)
    y_index = _channel_index(channels, y_channel)
    return [(event[x_index], event[y_index]) for event in events]


def _kmeans(points: list[tuple[float, float]], *, k: int, max_iter: int) -> tuple[list[int], list[tuple[float, float]]]:
    if len(points) < k:
        raise ValueError("event count must be greater than or equal to k")
    sorted_points = sorted(points)
    centroids = [sorted_points[round(index * (len(sorted_points) - 1) / (k - 1))] for index in range(k)]
    labels = [0 for _point in points]
    for _ in range(max_iter):
        new_labels = [_nearest_centroid(point, centroids) for point in points]
        if new_labels == labels:
            break
        labels = new_labels
        centroids = [_centroid([point for point, label in zip(points, labels) if label == cluster]) for cluster in range(k)]
    return labels, centroids


def _dbscan(points: list[tuple[float, float]], *, eps: float, min_samples: int) -> list[int]:
    labels = [-99 for _point in points]
    cluster_id = 0
    for point_index in range(len(points)):
        if labels[point_index] != -99:
            continue
        neighbors = _region_query(points, point_index, eps)
        if len(neighbors) < min_samples:
            labels[point_index] = -1
            continue
        labels[point_index] = cluster_id
        seeds = [neighbor for neighbor in neighbors if neighbor != point_index]
        while seeds:
            current = seeds.pop()
            if labels[current] == -1:
                labels[current] = cluster_id
            if labels[current] != -99:
                continue
            labels[current] = cluster_id
            current_neighbors = _region_query(points, current, eps)
            if len(current_neighbors) >= min_samples:
                for neighbor in current_neighbors:
                    if labels[neighbor] in {-99, -1} and neighbor not in seeds:
                        seeds.append(neighbor)
        cluster_id += 1
    return labels


def _agglomerative_centroid(
    points: list[tuple[float, float]],
    *,
    n_clusters: int,
) -> tuple[list[int], list[tuple[float, float]]]:
    if len(points) < n_clusters:
        raise ValueError("event count must be greater than or equal to n_clusters")
    clusters: list[list[int]] = [[index] for index in range(len(points))]
    while len(clusters) > n_clusters:
        best_pair: tuple[int, int] | None = None
        best_distance = math.inf
        for left_index in range(len(clusters)):
            for right_index in range(left_index + 1, len(clusters)):
                distance = _ward_distance(points, clusters[left_index], clusters[right_index])
                if distance < best_distance:
                    best_pair = (left_index, right_index)
                    best_distance = distance
        if best_pair is None:
            break
        left_index, right_index = best_pair
        clusters[left_index] = [*clusters[left_index], *clusters[right_index]]
        del clusters[right_index]
    labels = [0 for _point in points]
    centroids: list[tuple[float, float]] = []
    for label, cluster in enumerate(clusters):
        for point_index in cluster:
            labels[point_index] = label
        centroids.append(_centroid([points[point_index] for point_index in cluster]))
    return labels, centroids


def _density_valley(values: list[float], bins: int) -> tuple[float, float]:
    if len(values) < 3:
        raise ValueError("at least three values are required")
    minimum = min(values)
    maximum = max(values)
    if minimum == maximum:
        raise ValueError("density threshold requires a non-constant channel")
    width = (maximum - minimum) / bins
    counts = [0 for _ in range(bins)]
    for value in values:
        index = min(int((value - minimum) / width), bins - 1)
        counts[index] += 1
    peak_indices = sorted(range(bins), key=lambda index: counts[index], reverse=True)[:2]
    left_peak, right_peak = sorted(peak_indices)
    if left_peak == right_peak:
        raise ValueError("could not identify two density peaks")
    valley_range = range(left_peak + 1, right_peak)
    if not list(valley_range):
        valley_index = (left_peak + right_peak) // 2
    else:
        valley_index = min(valley_range, key=lambda index: counts[index])
    threshold = minimum + (valley_index + 0.5) * width
    peak_mean = (counts[left_peak] + counts[right_peak]) / 2.0
    separation = 0.0 if peak_mean == 0 else (peak_mean - counts[valley_index]) / peak_mean
    return threshold, separation


def _ellipse_gate_from_points(
    points: list[tuple[float, float]],
    x_channel: str,
    y_channel: str,
    *,
    scale: float,
    gate_name: str,
) -> dict[str, Any]:
    if not points:
        raise ValueError("cannot create gate from empty cluster")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "type": "ellipse",
        "name": gate_name,
        "x_channel": x_channel,
        "y_channel": y_channel,
        "center_x": _mean(xs),
        "center_y": _mean(ys),
        "radius_x": max(_stddev(xs) * scale, 1e-9),
        "radius_y": max(_stddev(ys) * scale, 1e-9),
        "angle_degrees": 0.0,
    }


def _rectangle_gate_from_points(
    points: list[tuple[float, float]],
    x_channel: str,
    y_channel: str,
    *,
    padding: float,
    gate_name: str,
) -> dict[str, Any]:
    if not points:
        raise ValueError("cannot create gate from empty cluster")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "type": "rectangle",
        "name": gate_name,
        "x_channel": x_channel,
        "y_channel": y_channel,
        "x_min": min(xs) - padding,
        "x_max": max(xs) + padding,
        "y_min": min(ys) - padding,
        "y_max": max(ys) + padding,
    }


def _cluster_confidence(
    points: list[tuple[float, float]],
    labels: list[int],
    target_label: int,
    target_centroid: tuple[float, float],
) -> ConfidenceScore:
    selected = [point for point, label in zip(points, labels) if label == target_label]
    other = [point for point, label in zip(points, labels) if label != target_label]
    compactness = _mean([_distance(point, target_centroid) for point in selected]) if selected else math.inf
    separation = min((_distance(target_centroid, point) for point in other), default=compactness)
    score = 1.0 if compactness == 0 else max(0.0, min(1.0, separation / (separation + compactness)))
    return _confidence_from_score(score, [f"cluster_fraction={len(selected) / len(points):.3f}"])


def _confidence_from_score(score: float, reasons: list[str]) -> ConfidenceScore:
    if score >= 0.75:
        level = "green"
    elif score >= 0.45:
        level = "yellow"
    else:
        level = "red"
    return ConfidenceScore(level=level, score=score, reasons=reasons)


def _select_cluster(labels: list[int], *, mode: str) -> int:
    clusters = sorted(set(labels))
    if mode == "largest":
        return max(clusters, key=lambda label: labels.count(label))
    if mode == "smallest":
        return min(clusters, key=lambda label: labels.count(label))
    try:
        label = int(mode)
    except ValueError as exc:
        raise ValueError("target_cluster must be largest, smallest, or a cluster index") from exc
    if label not in clusters:
        raise ValueError(f"target cluster {label} was not found")
    return label


def _region_query(points: list[tuple[float, float]], point_index: int, eps: float) -> list[int]:
    return [
        index
        for index, point in enumerate(points)
        if _distance(points[point_index], point) <= eps
    ]


def _ward_distance(points: list[tuple[float, float]], left: list[int], right: list[int]) -> float:
    left_centroid = _centroid([points[index] for index in left])
    right_centroid = _centroid([points[index] for index in right])
    return (len(left) * len(right) / (len(left) + len(right))) * (_distance(left_centroid, right_centroid) ** 2)


def _nearest_centroid(point: tuple[float, float], centroids: list[tuple[float, float]]) -> int:
    return min(range(len(centroids)), key=lambda index: _distance(point, centroids[index]))


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    return (_mean([point[0] for point in points]), _mean([point[1] for point in points]))


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _side_balance(values: list[float], threshold: float) -> float:
    left = len([value for value in values if value < threshold])
    right = len(values) - left
    return abs(left - right) / len(values)
