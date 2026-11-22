"""Tests de l'export CSV (aucune dépendance GTK)."""

from __future__ import annotations

import csv
import io
import os
import tempfile
import unittest

from gpx_analyzer.analysis import Split, TrackStats
from gpx_analyzer.csv_export import build_csv, suggest_csv_name, write_csv


class _FakeTrack:
    name = "Sortie dimanche"


class TestCsvExport(unittest.TestCase):
    def _stats(self) -> TrackStats:
        stats = TrackStats()
        stats.distance_km = 10.25
        stats.duration_s = 3661.0
        stats.moving_s = 3600.0
        stats.avg_moving_speed_kmh = 10.25
        stats.max_speed_kmh = 13.4
        stats.elevation_gain = 120.0
        stats.elevation_loss = 95.0
        stats.elevation_min = 42.0
        stats.elevation_max = 130.0
        stats.calories = 700
        stats.splits = [
            Split(number=1, distance=1000.0, start=None, end=None, duration=350.0, pace=5.833, gain=12.0)
        ]
        return stats

    def test_csv_is_semicolon_separated_and_parsable(self):
        text = build_csv(_FakeTrack(), self._stats(), weight_kg=72.0)
        rows = list(csv.reader(io.StringIO(text), delimiter=";"))
        self.assertEqual(rows[0][0], "Analyse GPX")
        self.assertEqual(rows[0][1], "Sortie dimanche")
        header_index = next(i for i, row in enumerate(rows) if row and row[0] == "Kilométriques")
        split_row = rows[header_index + 1]
        self.assertEqual(split_row[-1], "12")

    def test_decimal_comma(self):
        text = build_csv(_FakeTrack(), self._stats())
        self.assertIn("10,250", text)

    def test_write_csv_writes_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sortie.csv")
            write_csv(path, _FakeTrack(), self._stats())
            with open(path, "rb") as handle:
                data = handle.read()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))

    def test_suggest_csv_name(self):
        self.assertEqual(suggest_csv_name("matinée-plage!"), "matinée-plage.csv")


if __name__ == "__main__":
    unittest.main()
