from __future__ import annotations

import argparse
import os
import sys

from .analysis import build_report, compute_stats
from .gpx_parser import parse_gpx


def run_text(paths: list[str], weight_kg: float) -> int:
    exit_code = 0
    for path in paths:
        try:
            track = parse_gpx(path)
        except (OSError, ValueError) as error:
            print(f"Erreur : {path} : {error}", file=sys.stderr)
            exit_code = 1
            continue
        if not track.points:
            print(f"Erreur : {path} : aucune trace trouvée", file=sys.stderr)
            exit_code = 1
            continue
        stats = compute_stats(track, weight_kg)
        print(build_report(track, stats, weight_kg))
        print()
    return exit_code


def has_display() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="gpx-analyzer",
        description="Analyse de traces GPX de running : statistiques, splits, profil, carte.",
    )
    parser.add_argument("files", nargs="*", help="Fichiers GPX à analyser")
    parser.add_argument(
        "--texte",
        action="store_true",
        help="Afficher un rapport texte dans le terminal (sans interface graphique)",
    )
    parser.add_argument("--poids", type=float, default=70.0, help="Poids en kg pour l'estimation des calories")
    args = parser.parse_args(argv)

    if args.files and (args.texte or not has_display()):
        return run_text(args.files, args.poids)

    from .main_window import GpxAnalyzerApp

    raise SystemExit(GpxAnalyzerApp(args.files).run(None))


if __name__ == "__main__":
    main()
