"""OSRM client used by planning services.

Centralizes road-routing calls so generated plans use one source of truth for
distance, duration, route geometry, and per-leg itinerary data.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import requests


class OSRMError(RuntimeError):
    """Raised when OSRM cannot return a usable routing response."""


Coordinate = tuple[float, float]  # (lat, lon) in application code


@dataclass(frozen=True)
class OSRMTable:
    durations_sec: list[list[float]]
    distances_m: list[list[float]]

    @property
    def durations_min(self) -> list[list[float]]:
        return [[value / 60.0 for value in row] for row in self.durations_sec]

    @property
    def distances_km(self) -> list[list[float]]:
        return [[value / 1000.0 for value in row] for row in self.distances_m]


class OSRMService:
    def __init__(
        self,
        base_url: str | None = None,
        profile: str | None = None,
        timeout: float = 12.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("OSRM_BASE_URL") or "http://osrm:5000").rstrip("/")
        self.profile = profile or os.getenv("OSRM_PROFILE") or "driving"
        self.timeout = timeout
        self.session = session or requests.Session()
        self._table_cache: dict[str, OSRMTable] = {}
        self._route_cache: dict[str, dict[str, Any]] = {}

    def table(self, coordinates: Sequence[Coordinate]) -> OSRMTable:
        """Return OSRM duration/distance matrices for app-order coordinates."""
        coords = self._validate_coordinates(coordinates)
        if len(coords) < 2:
            raise OSRMError("OSRM table requires at least depot plus one stop")
        key = self._cache_key("table", coords)
        if key in self._table_cache:
            return self._table_cache[key]

        data = self._get(
            "table",
            coords,
            {"annotations": "duration,distance"},
        )
        durations = data.get("durations")
        distances = data.get("distances")
        if not isinstance(durations, list) or not isinstance(distances, list):
            raise OSRMError("OSRM table response is missing duration/distance matrices")
        self._ensure_complete_matrix(durations, "duration")
        self._ensure_complete_matrix(distances, "distance")

        table = OSRMTable(
            durations_sec=[[float(value) for value in row] for row in durations],
            distances_m=[[float(value) for value in row] for row in distances],
        )
        self._table_cache[key] = table
        return table

    def route(self, coordinates: Sequence[Coordinate]) -> dict[str, Any]:
        """Return one ordered route with geometry, totals, and normalized legs."""
        coords = self._validate_coordinates(coordinates)
        if len(coords) < 2:
            raise OSRMError("OSRM route requires at least two coordinates")
        key = self._cache_key("route", coords)
        if key in self._route_cache:
            return self._route_cache[key]

        data = self._get(
            "route",
            coords,
            {
                "steps": "true",
                "geometries": "geojson",
                "overview": "full",
                "annotations": "duration,distance",
            },
        )
        routes = data.get("routes")
        if not routes:
            raise OSRMError("OSRM route response did not contain a route")
        route = routes[0]
        legs = []
        for leg in route.get("legs") or []:
            legs.append({
                "distance_m": float(leg.get("distance") or 0.0),
                "distance_km": round(float(leg.get("distance") or 0.0) / 1000.0, 3),
                "duration_sec": float(leg.get("duration") or 0.0),
                "travel_min": int(round(float(leg.get("duration") or 0.0) / 60.0)),
                "steps": leg.get("steps") or [],
            })
        normalized = {
            "distance_m": float(route.get("distance") or 0.0),
            "total_distance_km": round(float(route.get("distance") or 0.0) / 1000.0, 3),
            "duration_sec": float(route.get("duration") or 0.0),
            "total_travel_min": int(round(float(route.get("duration") or 0.0) / 60.0)),
            "geometry": route.get("geometry"),
            "legs": legs,
        }
        self._route_cache[key] = normalized
        return normalized

    def nearest(self, coordinate: Coordinate) -> dict[str, Any]:
        coords = self._validate_coordinates([coordinate])
        return self._get("nearest", coords, {})

    def _get(
        self,
        service: str,
        coordinates: Sequence[Coordinate],
        params: dict[str, str],
    ) -> dict[str, Any]:
        encoded = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coordinates)
        url = f"{self.base_url}/{service}/v1/{self.profile}/{encoded}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise OSRMError(f"OSRM {service} request failed: {exc}") from exc
        except ValueError as exc:
            raise OSRMError(f"OSRM {service} returned invalid JSON") from exc
        code = data.get("code")
        if code not in {None, "Ok"}:
            message = data.get("message") or code
            raise OSRMError(f"OSRM {service} failed: {message}")
        return data

    @staticmethod
    def _validate_coordinates(coordinates: Iterable[Coordinate]) -> list[Coordinate]:
        validated: list[Coordinate] = []
        for raw in coordinates:
            try:
                lat = float(raw[0])
                lon = float(raw[1])
            except (TypeError, ValueError, IndexError) as exc:
                raise OSRMError("Missing or invalid coordinates") from exc
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                raise OSRMError(f"Coordinate out of range: {lat}, {lon}")
            validated.append((lat, lon))
        return validated

    @staticmethod
    def _ensure_complete_matrix(matrix: list[list[Any]], label: str) -> None:
        for row_idx, row in enumerate(matrix):
            if not isinstance(row, list):
                raise OSRMError(f"OSRM {label} matrix row {row_idx} is invalid")
            for col_idx, value in enumerate(row):
                if value is None:
                    raise OSRMError(
                        f"OSRM could not route matrix edge {row_idx}->{col_idx}"
                    )

    def _cache_key(self, service: str, coordinates: Sequence[Coordinate]) -> str:
        raw = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon in coordinates)
        payload = f"{service}:{self.profile}:{raw}"
        return hashlib.sha256(payload.encode("ascii")).hexdigest()
