"""
Routing Provider Abstraction Interface and Default Modeled Geographic Provider.
Supports pluggable routing services (e.g. OSRM, ORS, Google Maps) with fallback to
deterministic geographic distance modeling.
"""
from __future__ import annotations

import abc
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Literal, Optional


@dataclass(frozen=True)
class LocationCoordinate:
    """Represents a geographic point for route calculation."""
    label: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    district: Optional[str] = None
    taluka: Optional[str] = None

    @property
    def has_exact_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


@dataclass(frozen=True)
class RouteCalculationResult:
    """Result of a multi-waypoint route distance and transit time evaluation."""
    total_distance_km: Optional[Decimal]
    distance_certainty: Literal["VERIFIED_ROAD_DISTANCE", "MODELED_GEOGRAPHIC_DISTANCE", "UNAVAILABLE"]
    estimated_transit_hours: Optional[Decimal]
    transit_time_certainty: Literal["VERIFIED_ROAD_TIME", "MODELED_TRANSIT_ESTIMATE", "UNAVAILABLE"]
    segment_distances_km: List[Optional[Decimal]]
    provider_name: str
    is_live_routing: bool = False
    disclaimer: str = ""


class BaseRoutingProvider(abc.ABC):
    """Abstract base class for all routing providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Name of the routing engine/provider."""
        pass

    @abc.abstractmethod
    def calculate_route(self, waypoints: List[LocationCoordinate]) -> RouteCalculationResult:
        """Computes cumulative distance, transit time, and segment distances across ordered waypoints."""
        pass

    @abc.abstractmethod
    def get_distance_matrix(
        self,
        origins: List[LocationCoordinate],
        destinations: List[LocationCoordinate],
    ) -> List[List[Optional[Decimal]]]:
        """Computes point-to-point distance matrix between origins and destinations."""
        pass


class ModeledGeographicRoutingProvider(BaseRoutingProvider):
    """
    Default deterministic geographic routing provider.
    Uses Haversine distance with terrain routing factor (1.25x) and standard commercial
    transit speeds (35 km/h rural multi-stop, 50 km/h highway).
    """

    def __init__(self, road_factor: float = 1.25, avg_speed_kmh: float = 40.0) -> None:
        self.road_factor = road_factor
        self.avg_speed_kmh = avg_speed_kmh

    @property
    def provider_name(self) -> str:
        return "Modeled Geographic Distance Provider (Terrain Factor 1.25x)"

    def _calculate_haversine_segment(
        self,
        origin: LocationCoordinate,
        dest: LocationCoordinate,
    ) -> Optional[Decimal]:
        if not origin.has_exact_coordinates or not dest.has_exact_coordinates:
            # Fallback: if same district, approximate 25 km; if different district, approximate 65 km
            if origin.district and dest.district:
                if origin.district.strip().lower() == dest.district.strip().lower():
                    return Decimal("25.0")
                return Decimal("65.0")
            return None

        R = 6371.0  # Earth radius in km
        lat1 = math.radians(origin.latitude)
        lon1 = math.radians(origin.longitude)
        lat2 = math.radians(dest.latitude)
        lon2 = math.radians(dest.longitude)

        d_lat = lat2 - lat1
        d_lon = lon2 - lon1

        a = math.sin(d_lat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        direct_km = R * c
        road_km = max(direct_km * self.road_factor, 1.0)
        return Decimal(str(round(road_km, 2)))

    def calculate_route(self, waypoints: List[LocationCoordinate]) -> RouteCalculationResult:
        if len(waypoints) < 2:
            return RouteCalculationResult(
                total_distance_km=Decimal("0.0"),
                distance_certainty="MODELED_GEOGRAPHIC_DISTANCE",
                estimated_transit_hours=Decimal("0.0"),
                transit_time_certainty="MODELED_TRANSIT_ESTIMATE",
                segment_distances_km=[],
                provider_name=self.provider_name,
                is_live_routing=False,
                disclaimer="Route requires at least 2 waypoints.",
            )

        all_exact = all(w.has_exact_coordinates for w in waypoints)
        segment_distances: List[Optional[Decimal]] = []
        total_dist = Decimal("0.0")
        has_unresolvable = False

        for i in range(len(waypoints) - 1):
            seg_dist = self._calculate_haversine_segment(waypoints[i], waypoints[i + 1])
            segment_distances.append(seg_dist)
            if seg_dist is not None:
                total_dist += seg_dist
            else:
                has_unresolvable = True

        if has_unresolvable and total_dist == Decimal("0.0"):
            return RouteCalculationResult(
                total_distance_km=None,
                distance_certainty="UNAVAILABLE",
                estimated_transit_hours=None,
                transit_time_certainty="UNAVAILABLE",
                segment_distances_km=segment_distances,
                provider_name=self.provider_name,
                is_live_routing=False,
                disclaimer="One or more locations lack geographic information to model distance.",
            )

        total_distance = Decimal(str(round(total_dist, 2)))
        transit_hours = Decimal(str(round(float(total_distance) / self.avg_speed_kmh, 2)))

        return RouteCalculationResult(
            total_distance_km=total_distance,
            distance_certainty="MODELED_GEOGRAPHIC_DISTANCE",
            estimated_transit_hours=transit_hours,
            transit_time_certainty="MODELED_TRANSIT_ESTIMATE",
            segment_distances_km=segment_distances,
            provider_name=self.provider_name,
            is_live_routing=False,
            disclaimer=(
                "Distances and transit durations are modeled from terrain-adjusted geographic coordinates. "
                "Confirmed road network geometry and live ETAs require operational dispatch integration."
            ),
        )

    def get_distance_matrix(
        self,
        origins: List[LocationCoordinate],
        destinations: List[LocationCoordinate],
    ) -> List[List[Optional[Decimal]]]:
        matrix: List[List[Optional[Decimal]]] = []
        for o in origins:
            row: List[Optional[Decimal]] = []
            for d in destinations:
                row.append(self._calculate_haversine_segment(o, d))
            matrix.append(row)
        return matrix
