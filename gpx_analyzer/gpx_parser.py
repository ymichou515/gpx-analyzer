from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrackPoint:
    lat: float
    lon: float
    ele: float
    time: datetime | None = None
    distance: float = 0.0
    speed: float = 0.0


@dataclass
class Track:
    name: str
    points: list[TrackPoint]

    @property
    def distance(self) -> float:
        return self.points[-1].distance if self.points else 0.0


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_time(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def compute_derived(points: list[TrackPoint]) -> None:
    cumulative = 0.0
    for i, point in enumerate(points):
        if i == 0:
            point.distance = 0.0
            continue
        previous = points[i - 1]
        cumulative += haversine(previous.lat, previous.lon, point.lat, point.lon)
        point.distance = cumulative
        if point.time is not None and previous.time is not None:
            delta = (point.time - previous.time).total_seconds()
            point.speed = cumulative_delta(previous, point, delta)
        else:
            point.speed = 0.0


def cumulative_delta(previous: TrackPoint, current: TrackPoint, delta: float) -> float:
    if delta <= 0:
        return 0.0
    return haversine(previous.lat, previous.lon, current.lat, current.lon) / delta


def parse_gpx(path: str) -> Track:
    tree = ET.parse(path)
    root = tree.getroot()
    name = ""
    points: list[TrackPoint] = []
    for child in root:
        if _local(child.tag) != "trk":
            continue
        for item in child:
            if _local(item.tag) == "name" and not name:
                name = (item.text or "").strip()
            if _local(item.tag) != "trkseg":
                continue
            for trkpt in item:
                if _local(trkpt.tag) != "trkpt":
                    continue
                lat = float(trkpt.get("lat", "nan"))
                lon = float(trkpt.get("lon", "nan"))
                ele: float | None = None
                time: datetime | None = None
                for sub in trkpt:
                    tag = _local(sub.tag)
                    if tag == "ele" and sub.text:
                        ele = float(sub.text)
                    elif tag == "time" and sub.text:
                        time = _parse_time(sub.text.strip())
                if math.isnan(lat) or math.isnan(lon):
                    continue
                points.append(TrackPoint(lat=lat, lon=lon, ele=ele if ele is not None else 0.0, time=time))
    compute_derived(points)
    return Track(name=name or str(path), points=points)
