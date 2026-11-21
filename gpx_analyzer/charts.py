from __future__ import annotations

import math
from datetime import datetime, timezone

MARGIN = {"left": 58, "right": 18, "top": 34, "bottom": 34}

GRID = (0.88, 0.88, 0.88)
TEXT = (0.35, 0.35, 0.35)
TITLE = (0.20, 0.20, 0.20)
BLUE = (0.20, 0.45, 0.85)
BLUE_FILL = (0.20, 0.45, 0.85, 0.15)
GREEN = (0.15, 0.65, 0.30)
RED = (0.85, 0.25, 0.20)
ORANGE = (0.95, 0.55, 0.10)


def _plot_rect(w: float, h: float, margins=MARGIN):
    return margins["left"], margins["top"], w - margins["left"] - margins["right"], h - margins["top"] - margins["bottom"]


def _source(cr, color):
    if len(color) == 4:
        cr.set_source_rgba(*color)
    else:
        cr.set_source_rgb(*color)


def _text(cr, text: str, x: float, y: float, size: float = 10.0, color=TEXT, align: str = "left") -> None:
    cr.set_font_size(size)
    _source(cr, color)
    extents = cr.text_extents(text)
    if align == "center":
        x -= extents.width / 2
        y += extents.height / 2
    elif align == "right":
        x -= extents.width
        y += extents.height / 2
    else:
        y += extents.height
    cr.move_to(x, y)
    cr.show_text(text)


def _title(cr, text: str, x0: float, y0: float) -> None:
    _text(cr, text, x0, y0 - 14, size=12, color=TITLE, align="left")


def _x_step(total_km: float) -> float:
    for step in (0.5, 1.0, 2.0, 5.0, 10.0, 20.0):
        if total_km / step <= 10:
            return step
    return 50.0


def _grid_and_axis(cr, x0, y0, pw, ph, ymin, ymax, total_km):
    cr.set_line_width(1.0)
    for i in range(4):
        value = ymin + (ymax - ymin) * i / 3.0
        y = y0 + ph - (i / 3.0) * ph
        _source(cr, GRID)
        cr.move_to(x0, y)
        cr.line_to(x0 + pw, y)
        cr.stroke()
        _text(cr, f"{value:.0f}", x0 - 6, y, align="right")
    step = _x_step(total_km)
    km = step
    while km <= total_km + 1e-6:
        x = x0 + (km / total_km) * pw
        _source(cr, GRID)
        cr.move_to(x, y0)
        cr.line_to(x, y0 + ph)
        cr.stroke()
        _text(cr, f"{km:g}", x, y0 + ph + 6, align="center")
        km += step
    cr.rectangle(x0, y0, pw, ph)
    _source(cr, GRID)
    cr.stroke()
    _text(cr, "km", x0 + pw + 2, y0 + ph + 6, align="right")


def draw_elevation_profile(cr, width: float, height: float, track) -> None:
    x0, y0, pw, ph = _plot_rect(width, height)
    distances = [p.distance / 1000.0 for p in track.points]
    elevations = [p.ele for p in track.points]
    if len(elevations) < 2 or not distances or distances[-1] <= 0:
        _text(cr, "Pas de données d'altitude", width / 2, height / 2, align="center")
        return
    ymin = min(elevations)
    ymax = max(elevations)
    pad = max((ymax - ymin) * 0.08, 2.0)
    ymin -= pad
    ymax += pad
    total_km = distances[-1]
    _title(cr, "Altitude (m)", x0, y0)
    _grid_and_axis(cr, x0, y0, pw, ph, ymin, ymax, total_km)

    def scale(d, e):
        return (
            x0 + (d / total_km) * pw,
            y0 + ph - (e - ymin) / (ymax - ymin) * ph,
        )

    cr.set_line_width(1.6)
    first = True
    for d, e in zip(distances, elevations):
        x, y = scale(d, e)
        if first:
            cr.move_to(x, y)
            first = False
        else:
            cr.line_to(x, y)
    _source(cr, BLUE)
    cr.stroke_preserve()
    cr.line_to(x0 + pw, y0 + ph)
    cr.line_to(x0, y0 + ph)
    cr.close_path()
    _source(cr, BLUE_FILL)
    cr.fill()


def draw_pace_chart(cr, width: float, height: float, splits) -> None:
    x0, y0, pw, ph = _plot_rect(width, height)
    if not splits:
        _text(cr, "Pas de données temporelles", width / 2, height / 2, align="center")
        return
    paces = [s.pace for s in splits if s.pace]
    if not paces:
        _text(cr, "Pas de données temporelles", width / 2, height / 2, align="center")
        return
    pmin = min(paces)
    pmax = max(paces)
    pad = max((pmax - pmin) * 0.15, 0.15)
    top = max(pmin - pad, 0.5)
    bottom = pmax + pad
    span = bottom - top

    def scale(pace):
        frac = (pace - top) / span
        return y0 + max(min(frac, 1.0), 0.0) * ph

    cr.set_line_width(1.0)
    for i in range(4):
        pace = top + span * i / 3.0
        y = y0 + (i / 3.0) * ph
        _source(cr, GRID)
        cr.move_to(x0, y)
        cr.line_to(x0 + pw, y)
        cr.stroke()
        minutes = int(pace)
        seconds = int(round((pace - minutes) * 60))
        _text(cr, f"{minutes}:{seconds:02d}", x0 - 6, y, align="right")

    bar_area = pw / len(splits)
    bar_width = max(bar_area * 0.6, 2.0)
    best = min(paces)
    for index, split in enumerate(splits):
        if not split.pace:
            continue
        x = x0 + index * bar_area + (bar_area - bar_width) / 2
        y = scale(split.pace)
        _source(cr, GREEN if abs(split.pace - best) < 1e-9 else BLUE)
        cr.rectangle(x, y, bar_width, y0 + ph - y)
        cr.fill()
        if len(splits) <= 20:
            _text(cr, str(split.number), x + bar_width / 2, y0 + ph + 6, align="center")
    _text(cr, "km", x0 + pw + 4, y0 + ph + 6, align="right")


def draw_track_map(cr, width: float, height: float, track) -> None:
    x0, y0, pw, ph = _plot_rect(width, height)
    points = track.points
    if len(points) < 2:
        _text(cr, "Trace trop courte", width / 2, height / 2, align="center")
        return
    lats = [p.lat for p in points]
    lons = [p.lon for p in points]
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)
    mid_lat = math.radians((lat_min + lat_max) / 2)
    width_m = max((lon_max - lon_min) * 111320.0 * math.cos(mid_lat), 1.0)
    height_m = max((lat_max - lat_min) * 110540.0, 1.0)
    scale_m = min(pw / width_m, ph / height_m)
    offset_x = x0 + (pw - width_m * scale_m) / 2
    offset_y = y0 + (ph - height_m * scale_m) / 2

    def project(p):
        return (
            offset_x + (p.lon - lon_min) * 111320.0 * math.cos(mid_lat) * scale_m,
            offset_y + (lat_max - p.lat) * 110540.0 * scale_m,
        )

    _title(cr, "Parcours", x0, y0)
    cr.set_line_width(2.2)
    cr.set_line_join(1)
    first = True
    for point in points:
        x, y = project(point)
        if first:
            cr.move_to(x, y)
            first = False
        else:
            cr.line_to(x, y)
    _source(cr, BLUE)
    cr.stroke()

    for point, color in ((points[0], GREEN), (points[-1], RED)):
        x, y = project(point)
        cr.arc(x, y, 5.0, 0.0, 2 * math.pi)
        _source(cr, color)
        cr.fill()
