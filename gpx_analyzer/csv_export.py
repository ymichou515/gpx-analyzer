"""Export CSV des données d'analyse, lisible dans LibreOffice Calc.

Le fichier utilise le point-virgule comme séparateur, la virgule comme
séparateur décimal et l'encodage UTF-8 avec BOM : un double-clic suffit à
l'ouverture dans LibreOffice Calc (ou Excel) sans assistant d'import.
"""

from __future__ import annotations

import csv
import io
import re

from .analysis import TrackStats, fmt_pace, fmt_seconds


def suggest_csv_name(track_name: str) -> str:
    """Propose un nom de fichier CSV a partir du nom de la trace."""
    base = re.sub(r"[^\w\- ]+", "", track_name).strip() or "trace"
    return f"{base}.csv"


def _num(value: float | None, digits: int = 2) -> str:
    """Formate un nombre avec separateur decimal virgule ('' si absent)."""
    if value is None:
        return ""
    return f"{value:.{digits}f}".replace(".", ",")


def build_csv(track, stats: TrackStats, weight_kg: float = 70.0) -> str:
    """Construit le contenu CSV : resume puis table des kilometres."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")

    writer.writerow(["Analyse GPX", track.name])

    writer.writerow([])
    writer.writerow(["Résumé", "Valeur"])
    writer.writerow(["Distance (km)", _num(stats.distance_km, 3)])
    writer.writerow(["Durée totale (hh:mm:ss)", fmt_seconds(stats.duration_s)])
    writer.writerow(["Temps en mouvement (hh:mm:ss)", fmt_seconds(stats.moving_s)])

    avg_pace = 60.0 / stats.avg_moving_speed_kmh if stats.avg_moving_speed_kmh else None
    writer.writerow(["Allure moyenne (min:sec/km)", fmt_pace(avg_pace)])
    writer.writerow(["Meilleure allure (min:sec/km)", fmt_pace(stats.best_pace)])
    writer.writerow(["Vitesse moyenne (km/h)", _num(stats.avg_moving_speed_kmh, 1)])
    writer.writerow(["Vitesse maximale (km/h)", _num(stats.max_speed_kmh, 1)])
    writer.writerow(["Dénivelé positif (m)", _num(stats.elevation_gain, 0)])
    writer.writerow(["Dénivelé négatif (m)", _num(stats.elevation_loss, 0)])
    writer.writerow(["Altitude minimale (m)", _num(stats.elevation_min, 0)])
    writer.writerow(["Altitude maximale (m)", _num(stats.elevation_max, 0)])
    writer.writerow(["Calories estimées (kcal)", str(stats.calories)])
    writer.writerow(["Poids utilisé (kg)", _num(weight_kg, 0)])

    writer.writerow([])
    writer.writerow(["Kilométriques", "Temps", "Allure", "D+ (m)"])
    for split in stats.splits:
        writer.writerow(
            [
                split.label,
                fmt_seconds(split.duration),
                fmt_pace(split.pace),
                _num(split.gain, 0),
            ]
        )

    return buffer.getvalue()


def write_csv(path: str, track, stats: TrackStats, weight_kg: float = 70.0) -> None:
    """Écrit le CSV sur disque (UTF-8 avec BOM, fins de ligne CRLF pour Calc)."""
    text = build_csv(track, stats, weight_kg)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write(text.replace("\n", "\r\n"))
