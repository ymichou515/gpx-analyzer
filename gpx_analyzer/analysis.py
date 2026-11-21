from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


MOVING_SPEED_THRESHOLD = 0.8
MIN_RUNNING_SPEED_KMH = 3.0
ELEVATION_DEADBAND = 1.0


@dataclass
class Split:
    number: int
    distance: float
    start: datetime | None
    end: datetime | None
    duration: float | None
    pace: float | None
    gain: float

    @property
    def label(self) -> str:
        if self.distance < 999.0:
            return f"{self.number - 1} → {self.number} (partiel)"
        return f"km {self.number}"


@dataclass
class TrackStats:
    distance_km: float = 0.0
    duration_s: float = 0.0
    moving_s: float = 0.0
    elevation_gain: float = 0.0
    elevation_loss: float = 0.0
    elevation_min: float = 0.0
    elevation_max: float = 0.0
    avg_speed_kmh: float = 0.0
    avg_moving_speed_kmh: float = 0.0
    max_speed_kmh: float = 0.0
    best_pace: float | None = None
    calories: int = 0
    splits: list[Split] = field(default_factory=list)


def smooth(values: list[float], window: int = 9) -> list[float]:
    if window < 3 or len(values) < 3:
        return list(values)
    width = min(window, len(values))
    if width % 2 == 0:
        width -= 1
    if width < 3:
        width = 3
    half = width // 2
    result = []
    for i, _ in enumerate(values):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        result.append(sum(values[lo:hi]) / (hi - lo))
    return result


def _elevation_changes(values: list[float], deadband: float = ELEVATION_DEADBAND) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    gain = loss = 0.0
    direction = 0
    valley = peak = values[0]
    for value in values[1:]:
        if direction == 0:
            if value > peak:
                peak = value
            if value < valley:
                valley = value
            if peak - valley >= deadband:
                if peak == value:
                    gain += peak - valley
                    direction = 1
                    valley = value
                elif valley == value:
                    loss += peak - valley
                    direction = -1
                    peak = value
        elif direction == 1:
            if value >= peak:
                peak = value
            elif peak - value >= deadband:
                gain += peak - valley
                direction = -1
                valley = value
        else:
            if value <= valley:
                valley = value
            elif value - valley >= deadband:
                loss += peak - valley
                direction = 1
                peak = value
    if direction == 1:
        gain += peak - valley
    elif direction == -1:
        loss += peak - valley
    return gain, loss


def compute_stats(track, weight_kg: float = 70.0) -> TrackStats:
    stats = TrackStats()
    points = track.points
    if not points:
        return stats

    elevations = smooth([p.ele for p in points])
    speeds = smooth([p.speed for p in points])

    stats.distance_km = points[-1].distance / 1000.0
    stats.elevation_min = min(elevations)
    stats.elevation_max = max(elevations)

    stats.elevation_gain, stats.elevation_loss = _elevation_changes(elevations)

    if points[0].time is not None and points[-1].time is not None:
        stats.duration_s = (points[-1].time - points[0].time).total_seconds()

    duration_total = 0.0
    for point, previous in zip(points[1:], points):
        if point.time is None or previous.time is None:
            continue
        delta = (point.time - previous.time).total_seconds()
        if delta <= 0:
            continue
        duration_total += delta
        if point.speed > MOVING_SPEED_THRESHOLD:
            stats.moving_s += delta

    if stats.duration_s > 0:
        stats.avg_speed_kmh = stats.distance_km / (stats.duration_s / 3600.0)
    if stats.moving_s > 0:
        stats.avg_moving_speed_kmh = stats.distance_km / (stats.moving_s / 3600.0)

    if speeds:
        stats.max_speed_kmh = max(speeds) * 3.6
    best = 0.0
    for value in speeds:
        best = max(best, value * 3.6)
    if best > MIN_RUNNING_SPEED_KMH:
        stats.best_pace = 60.0 / best

    stats.splits = compute_splits(points, elevations)
    stats.calories = estimate_calories(stats, elevations[0], elevations[-1], weight_kg)
    return stats


def compute_splits(points, elevations) -> list[Split]:
    if points[0].time is None or points[-1].time is None:
        return []
    total = points[-1].distance
    marks = [k * 1000.0 for k in range(1, int(total // 1000) + 1)]
    if not marks or total > marks[-1] + 50.0:
        marks.append(total)
    splits: list[Split] = []
    start_dist = 0.0
    start_time = points[0].time
    for number, mark in enumerate(marks, start=1):
        end_time = _time_at(mark, points)
        duration = None
        if end_time is not None:
            duration = (end_time - start_time).total_seconds()
        split = Split(
            number=number,
            distance=mark - start_dist,
            start=start_time,
            end=end_time,
            duration=duration,
            pace=_pace_from(distance=mark - start_dist, duration=duration),
            gain=_segment_gain(points, elevations, start_dist, mark),
        )
        splits.append(split)
        start_dist = mark
        start_time = end_time if end_time is not None else points[-1].time
    return splits


def _segment_gain(points, elevations, start_dist, end_dist) -> float:
    segment_values = [
        e
        for p, e in zip(points, elevations)
        if start_dist <= p.distance <= end_dist
    ]
    if len(segment_values) < 2:
        return 0.0
    return _elevation_changes(segment_values)[0]


def _time_at(distance: float, points):
    if distance <= 0:
        return points[0].time
    for i in range(1, len(points)):
        if points[i].distance >= distance:
            previous = points[i - 1]
            segment = points[i].distance - previous.distance
            if segment <= 0 or previous.time is None or points[i].time is None:
                return points[i].time
            fraction = (distance - previous.distance) / segment
            seconds = (points[i].time - previous.time).total_seconds()
            return previous.time + timedelta(seconds=fraction * seconds)
    return points[-1].time


def _pace_from(distance: float, duration: float | None) -> float | None:
    if not duration or duration <= 0 or distance <= 0:
        return None
    return duration / 60.0 * (1000.0 / distance)


def estimate_calories(stats: TrackStats, start_elev: float, end_elev: float, weight_kg: float) -> int:
    if stats.moving_s <= 0 or stats.distance_km <= 0:
        return 0
    speed_min_per_km = 1000.0 / (stats.avg_moving_speed_kmh * 1000.0 / 60.0)
    speed_m_per_min = 1000.0 / speed_min_per_km
    grade = (end_elev - start_elev) / (stats.distance_km * 1000.0)
    grade = max(-1.0, min(1.0, grade))
    vo2 = 0.2 * speed_m_per_min + 0.9 * speed_m_per_min * grade + 3.5
    met = max(vo2 / 3.5, 1.0)
    hours = stats.moving_s / 3600.0
    return int(met * weight_kg * hours)


def fmt_seconds(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def fmt_pace(pace: float | None) -> str:
    if not pace or pace <= 0 or pace > 60.0:
        return "—"
    minutes = int(pace)
    seconds = int(round((pace - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d} /km"


def fmt_distance(distance_km: float) -> str:
    return f"{distance_km:.2f} km"


def build_report(track, stats: TrackStats, weight_kg: float = 70.0) -> str:
    lines = [f"Trace : {track.name}", ""]
    lines.append(f"Distance          : {fmt_distance(stats.distance_km)}")
    lines.append(f"Durée totale      : {fmt_seconds(stats.duration_s)}")
    lines.append(f"Temps en mouvement: {fmt_seconds(stats.moving_s)}")
    lines.append(f"Allure moyenne    : {fmt_pace(60.0 / stats.avg_moving_speed_kmh if stats.avg_moving_speed_kmh else None)}")
    lines.append(f"Meilleure allure  : {fmt_pace(stats.best_pace)}")
    lines.append(f"Vitesse moyenne   : {stats.avg_moving_speed_kmh:.1f} km/h (max {stats.max_speed_kmh:.1f})")
    lines.append(
        f"Dénivelé          : +{stats.elevation_gain:.0f} m / -{stats.elevation_loss:.0f} m "
        f"(alt. {stats.elevation_min:.0f} → {stats.elevation_max:.0f} m)"
    )
    lines.append(f"Calories estimées : ≈ {stats.calories} kcal (poids {weight_kg:.0f} kg)")
    if stats.splits:
        lines.append("")
        lines.append("Kilométriques :")
        for split in stats.splits:
            label = f"{split.label}".ljust(12)
            lines.append(
                f"  {label} {fmt_seconds(split.duration)}  {fmt_pace(split.pace)}  +{split.gain:.0f} m"
            )
    return "\n".join(lines)
