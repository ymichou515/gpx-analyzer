from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

from gpx_analyzer import analysis
from gpx_analyzer.gpx_parser import Track, TrackPoint, compute_derived, parse_gpx


START = datetime(2025, 1, 1, 8, 0, 0, tzinfo=timezone.utc)


def make_track(n: int, step_m: float, dt_s: float, elevation=None) -> Track:
    points = []
    for i in range(n):
        level = elevation(i * step_m) if elevation else 100.0
        points.append(
            TrackPoint(
                lat=0.0,
                lon=(i * step_m) / 111320.0,
                ele=level,
                time=START + timedelta(seconds=i * dt_s),
            )
        )
    compute_derived(points)
    return Track(name="test", points=points)


class ParserTest(unittest.TestCase):
    def test_parse_minimal_gpx(self):
        import math

        path = os.path.join(os.path.dirname(__file__), "data", "minimal.gpx")
        track = parse_gpx(path)
        self.assertEqual(track.name, "TestTrace")
        self.assertEqual(len(track.points), 5)
        expected = 4 * 111.32 * math.cos(math.radians(45.0))
        self.assertAlmostEqual(track.distance, expected, delta=5.0)

    def test_missing_time_is_tolerated(self):
        times = {0: START, 4: START + timedelta(seconds=120)}
        points = [
            TrackPoint(lat=45.0, lon=0.001 * i, ele=10.0, time=times.get(i))
            for i in range(5)
        ]
        compute_derived(points)
        track = Track(name="t", points=points)
        stats = analysis.compute_stats(track)
        self.assertEqual(stats.duration_s, 120.0)
        self.assertEqual(len(stats.splits), 1)
        self.assertAlmostEqual(stats.splits[0].duration, 120.0)


class AnalysisTest(unittest.TestCase):
    def test_distance(self):
        track = make_track(101, 100.0, 33.0)
        stats = analysis.compute_stats(track)
        self.assertAlmostEqual(stats.distance_km, 10.0, delta=0.05)

    def test_splits_calm_pace(self):
        track = make_track(301, 100.0, 33.0)
        stats = analysis.compute_stats(track)
        complete = [s for s in stats.splits if s.distance > 999.0]
        self.assertEqual(len(complete), 29)
        last = stats.splits[-1]
        self.assertLess(last.distance, 1000.0)
        self.assertGreater(last.distance, 900.0)
        for split in complete:
            self.assertAlmostEqual(split.pace, 5.5, delta=0.2)
            self.assertAlmostEqual(split.duration, 330.0, delta=5.0)

    def test_elevation_gain_synthetic_hill(self):
        def elevation(distance):
            return 100.0 + distance / 100.0

        track = make_track(101, 100.0, 33.0, elevation=elevation)
        stats = analysis.compute_stats(track)
        self.assertAlmostEqual(stats.elevation_gain, 100.0, delta=8.0)
        self.assertLessEqual(stats.elevation_loss, 1.0)

    def test_flat_track_gain_near_zero(self):
        track = make_track(200, 100.0, 33.0, elevation=lambda d: 50.0)
        stats = analysis.compute_stats(track)
        self.assertLessEqual(stats.elevation_gain, 2.0)
        self.assertLessEqual(stats.elevation_loss, 2.0)

    def test_partial_last_km(self):
        track = make_track(64, 100.0, 33.0)
        stats = analysis.compute_stats(track)
        last = stats.splits[-1]
        self.assertAlmostEqual(last.distance, 300.0, delta=30.0)


class FormattingTest(unittest.TestCase):
    def test_fmt_pace(self):
        self.assertEqual(analysis.fmt_pace(5.5), "5:30 /km")
        self.assertEqual(analysis.fmt_pace(None), "—")
        self.assertEqual(analysis.fmt_pace(0.0), "—")

    def test_fmt_seconds(self):
        self.assertEqual(analysis.fmt_seconds(59.6), "01:00")
        self.assertEqual(analysis.fmt_seconds(3661.0), "1:01:01")
        self.assertEqual(analysis.fmt_seconds(None), "—")

    def test_calories_positive_when_moving(self):
        track = make_track(101, 100.0, 33.0)
        stats = analysis.compute_stats(track, weight_kg=70.0)
        self.assertGreater(stats.calories, 300)
        self.assertLess(stats.calories, 1500)


if __name__ == "__main__":
    unittest.main()
