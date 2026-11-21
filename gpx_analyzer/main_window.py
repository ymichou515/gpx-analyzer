from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GLib, Gtk

from . import charts
from .analysis import TrackStats, compute_stats, fmt_distance, fmt_pace, fmt_seconds
from .gpx_parser import Track, parse_gpx


SUMMARY_ROWS = [
    "Distance",
    "Durée totale",
    "Temps en mouvement",
    "Allure moyenne",
    "Meilleure allure",
    "Vitesse moyenne (max)",
    "Dénivelé + / −",
    "Altitude min / max",
    "Calories estimées",
]


class GpxAnalyzerApp(Gtk.Application):
    def __init__(self, files=None):
        super().__init__(application_id="fr.gpxanalyzer.GpxAnalyzer")
        self.files = files or []

    def do_activate(self):
        window = GpxAnalyzerWindow(application=self)
        window.present()
        if self.files:
            window.load_paths(self.files)


class GpxAnalyzerWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Analyse GPX")
        self.set_default_size(1000, 720)
        self.tracks: list[tuple[Track, TrackStats]] = []
        self.current_index = 0
        self.weight = 70.0

        header = Gtk.HeaderBar()
        open_button = Gtk.Button(label="Ouvrir…")
        open_button.connect("clicked", self.on_open)
        header.pack_start(open_button)

        self.track_selector = Gtk.DropDown()
        self.track_selector.set_visible(False)
        self.track_selector.connect("notify::selected", self.on_track_selected)
        header.set_title_widget(self.track_selector)
        self.set_titlebar(header)

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.root.set_margin_top(6)
        self.root.set_margin_bottom(6)
        self.root.set_margin_start(6)
        self.root.set_margin_end(6)
        self.set_child(self.root)

        self.switcher = Gtk.StackSwitcher()
        self.switcher.set_visible(False)
        self.root.append(self.switcher)

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.root.append(self.stack)

        self.welcome = Gtk.Label(label="Ouvrez un ou plusieurs fichiers GPX pour analyser vos sorties.")
        self.stack.add_titled(self.welcome, "welcome", "Bienvenue")

        self.summary_page = None
        self.summary_values: dict[str, Gtk.Label] = {}
        self.splits_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.profile_area = Gtk.DrawingArea()
        self.profile_area.set_draw_func(self.on_profile_draw)
        self.map_area = Gtk.DrawingArea()
        self.map_area.set_draw_func(self.on_map_draw)

    @property
    def current(self) -> tuple[Track, TrackStats] | None:
        if not self.tracks or self.current_index >= len(self.tracks):
            return None
        return self.tracks[self.current_index]

    def on_open(self, button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        gpx_filter = Gtk.FileFilter()
        gpx_filter.set_name("Traces GPX")
        gpx_filter.add_pattern("*.gpx")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(gpx_filter)
        dialog.set_filters(filters)
        dialog.open_multiple(self, None, self.on_files_opened)

    def on_files_opened(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return
        paths = [f.get_path() for f in files if f.get_path()]
        self.load_paths(paths)

    def load_paths(self, paths: list[str]) -> None:
        errors = []
        for path in paths:
            try:
                track = parse_gpx(path)
            except (OSError, ValueError) as error:
                errors.append(f"{os.path.basename(path)} : {error}")
                continue
            if not track.points:
                errors.append(f"{os.path.basename(path)} : aucune trace trouvée")
                continue
            self.tracks.append((track, compute_stats(track, self.weight)))
        if errors:
            self.show_error("\n".join(errors))
        self.rebuild_interface()

    def show_error(self, message: str) -> None:
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, text=message, buttons=Gtk.ButtonsType.OK)
        dialog.present()
        dialog.connect("response", lambda d, _response: d.destroy())

    def on_track_selected(self, dropdown: Gtk.DropDown, _pspec) -> None:
        position = dropdown.get_selected()
        if position == Gtk.INVALID_LIST_POSITION:
            return
        self.current_index = position
        self.refresh_all()

    def rebuild_interface(self) -> None:
        if not self.tracks:
            self.track_selector.set_visible(False)
            return
        if self.summary_page is None:
            self.stack.remove(self.welcome)
            self._add_pages()
        names = [
            f"{track.name} ({track.distance / 1000.0:.1f} km)"
            for track, _stats in self.tracks
        ]
        self.current_index = len(self.tracks) - 1
        self.track_selector.set_model(Gtk.StringList.new(names))
        self.track_selector.set_selected(self.current_index)
        self.track_selector.set_visible(True)
        self.switcher.set_visible(True)
        self.refresh_all()

    def _add_pages(self) -> None:
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.build_summary_page())
        scroller.set_vexpand(True)
        self.summary_page = scroller
        self.stack.add_titled(scroller, "summary", "Résumé")

        splits_scroller = Gtk.ScrolledWindow()
        splits_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        splits_scroller.set_child(self.splits_box)
        splits_scroller.set_vexpand(True)
        self.stack.add_titled(splits_scroller, "splits", "Kilométriques")

        self.stack.add_titled(self.profile_area, "profile", "Profil")
        self.stack.add_titled(self.map_area, "map", "Carte")

    def build_summary_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        weight_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        weight_label = Gtk.Label(label="Poids (kg) :")
        weight_row.append(weight_label)
        weight_spin = Gtk.SpinButton.new_with_range(30.0, 200.0, 1.0)
        weight_spin.set_value(self.weight)
        weight_spin.connect("value-changed", self.on_weight_changed)
        weight_row.append(weight_spin)
        box.append(weight_row)

        grid = Gtk.Grid(column_spacing=16, row_spacing=10)
        grid.set_column_homogeneous(False)
        for row, name in enumerate(SUMMARY_ROWS):
            name_label = Gtk.Label(label=name)
            name_label.set_xalign(0.0)
            name_label.add_css_class("dim-label")
            value_label = Gtk.Label(label="—")
            value_label.set_xalign(0.0)
            self.summary_values[name] = value_label
            grid.attach(name_label, 0, row, 1, 1)
            grid.attach(value_label, 1, row, 1, 1)
        box.append(grid)
        return box

    def on_weight_changed(self, spin: Gtk.SpinButton) -> None:
        self.weight = spin.get_value()
        self.tracks = [
            (track, compute_stats(track, self.weight)) for track, _stats in self.tracks
        ]
        self.refresh_all()

    def refresh_all(self) -> None:
        entry = self.current
        if entry is None:
            return
        track, stats = entry
        self.refresh_summary(stats)
        self.refresh_splits(stats)
        self.profile_area.queue_draw()
        self.map_area.queue_draw()

    def refresh_summary(self, stats: TrackStats) -> None:
        values = {
            "Distance": fmt_distance(stats.distance_km),
            "Durée totale": fmt_seconds(stats.duration_s),
            "Temps en mouvement": fmt_seconds(stats.moving_s),
            "Allure moyenne": fmt_pace(60.0 / stats.avg_moving_speed_kmh) if stats.avg_moving_speed_kmh else "—",
            "Meilleure allure": fmt_pace(stats.best_pace),
            "Vitesse moyenne (max)": f"{stats.avg_moving_speed_kmh:.1f} km/h ({stats.max_speed_kmh:.1f})",
            "Dénivelé + / −": f"+{stats.elevation_gain:.0f} m / -{stats.elevation_loss:.0f} m",
            "Altitude min / max": f"{stats.elevation_min:.0f} m / {stats.elevation_max:.0f} m",
            "Calories estimées": f"{stats.calories} kcal ({self.weight:.0f} kg)",
        }
        for name, label in self.summary_values.items():
            label.set_text(values.get(name, "—"))

    def refresh_splits(self, stats: TrackStats) -> None:
        self.splits_box.set_margin_top(18)
        self.splits_box.set_margin_bottom(18)
        self.splits_box.set_margin_start(18)
        self.splits_box.set_margin_end(18)

        child = self.splits_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.splits_box.remove(child)
            child = next_child

        grid = Gtk.Grid(column_spacing=22, row_spacing=8)
        headers = ["Segment", "Temps", "Allure", "D+ "]
        for column, header_text in enumerate(headers):
            label = Gtk.Label(label=header_text)
            label.set_xalign(0.0)
            label.add_css_class("heading")
            grid.attach(label, column, 0, 1, 1)
        for row, split in enumerate(stats.splits, start=1):
            pace = fmt_pace(split.pace)
            duration = fmt_seconds(split.duration)
            cells = [split.label, duration, pace, f"+{split.gain:.0f} m"]
            for column, cell_text in enumerate(cells):
                label = Gtk.Label(label=cell_text)
                label.set_xalign(0.0)
                grid.attach(label, column, row, 1, 1)
        self.splits_box.append(grid)

    def on_profile_draw(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        entry = self.current
        if entry is None:
            return
        track, stats = entry
        height_top = height * 0.55
        height_bottom = height - height_top
        cr.save()
        cr.translate(0.0, 0.0)
        charts.draw_elevation_profile(cr, width, height_top, track)
        cr.restore()
        cr.save()
        cr.translate(0.0, height_top)
        charts.draw_pace_chart(cr, width, height_bottom, stats.splits)
        cr.restore()

    def on_map_draw(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        entry = self.current
        if entry is None:
            return
        charts.draw_track_map(cr, width, height, entry[0])
