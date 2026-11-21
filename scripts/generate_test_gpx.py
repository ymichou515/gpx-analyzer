from __future__ import annotations

import argparse
import math
import os
import random
from datetime import datetime, timedelta, timezone

STEP_S = 6.0


def pace_profile(distance_m: float, grade: float) -> float:
    base_speed = 3.05 + 0.35 * math.sin(distance_m / 2100.0) - 0.3 * math.exp(-((distance_m % 3800.0) / 900.0) ** 2)
    base_speed -= 3.5 * grade
    return max(1.9, min(4.6, base_speed))


def elevation_profile(distance_m: float) -> float:
    return (
        85.0
        + 28.0 * math.sin(distance_m / 1250.0)
        + 9.0 * math.sin(distance_m / 340.0 + 1.3)
        + 2.5 * math.sin(distance_m / 90.0)
    )


def build_points(total_km: float, rng: random.Random):
    total_m = total_km * 1000.0
    points = []
    distance = 0.0
    elapsed = 0
    elevation = elevation_profile(0.0)
    while distance < total_m:
        prev_elevation = elevation
        elevation = elevation_profile(distance)
        grade = (elevation - prev_elevation) / max(STEP_S * pace_profile(distance, 0.0), 1.0)
        speed = pace_profile(distance, max(-0.12, min(0.12, grade)))
        speed += rng.gauss(0.0, 0.08)
        distance += speed * STEP_S
        elapsed += STEP_S
        points.append(
            {
                "lat": 45.1880 + (elapsed / 30.0) * 0.0008 + 0.00018 * math.sin(distance / 800.0),
                "lon": 5.7240 + (elapsed / 30.0) * 0.0008 + 0.00018 * math.cos(distance / 950.0),
                "ele": elevation_profile(distance) + rng.gauss(0.0, 0.6),
                "time": elapsed,
            }
        )
    return points


def write_gpx(path: str, points, name: str) -> None:
    start = datetime(2025, 11, 16, 8, 12, 0, tzinfo=timezone.utc)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="gpx-analyzer-demo" xmlns="http://www.topografix.com/GPX/1/1">',
        "  <trk>",
        f"    <name>{name}</name>",
        "    <trkseg>",
    ]
    for point in points:
        timestamp = (start + timedelta(seconds=point["time"])).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(
            f'      <trkpt lat="{point["lat"]:.6f}" lon="{point["lon"]:.6f}">'
            f'<ele>{point["ele"]:.2f}</ele><time>{timestamp}</time></trkpt>'
        )
    lines += ["    </trkseg>", "  </trk>", "</gpx>"]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère des traces GPX de running pour tester gpx-analyzer.")
    parser.add_argument("output", nargs="?", default="examples/demo.gpx")
    parser.add_argument("--km", type=float, default=10.2, help="Distance de la course en km")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    directory = os.path.dirname(args.output)
    if directory:
        os.makedirs(directory, exist_ok=True)
    rng = random.Random(args.seed)
    points = build_points(args.km, rng)
    write_gpx(args.output, points, f"Course de test {args.km:.1f} km")
    print(f"Trace écrite : {args.output} ({len(points)} points)")


if __name__ == "__main__":
    main()
