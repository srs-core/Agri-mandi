"""
Phase 2E - Step 5: Route Optimization Interfaces and OR-Tools VRP Solver.
Pluggable optimization architecture for multi-stop agricultural produce collection routes.
"""
from __future__ import annotations

import abc
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.models.entities import Location, ShipmentPlanPickupStop
from app.modules.logistics.routing_providers import (
    BaseRoutingProvider,
    LocationCoordinate,
    RouteCalculationResult,
)


@dataclass(frozen=True)
class OptimizationExecutionResult:
    """Raw result of route optimization solver execution."""
    success: bool
    status: str
    ordered_stops: List[ShipmentPlanPickupStop]
    error_message: Optional[str] = None
    solver_name: str = "Google OR-Tools VRP"


class BaseRouteOptimizer(abc.ABC):
    """Abstract base class for multi-stop vehicle route optimization solvers."""

    @property
    @abc.abstractmethod
    def optimizer_name(self) -> str:
        """Name and version of the optimization solver."""
        pass

    @abc.abstractmethod
    def optimize(
        self,
        stops: List[ShipmentPlanPickupStop],
        destination_loc: Location,
        routing_provider: BaseRoutingProvider,
        vehicle_capacity_quintals: Optional[Decimal] = None,
        delivery_deadline: Optional[date] = None,
    ) -> OptimizationExecutionResult:
        """Determines the optimal visiting order of pickup stops to reach the destination."""
        pass


class DeterministicBaselineRouteOptimizer(BaseRouteOptimizer):
    """Baseline optimizer that preserves the planned sequence / Nearest Neighbor heuristic."""

    @property
    def optimizer_name(self) -> str:
        return "Deterministic Baseline Heuristic"

    def optimize(
        self,
        stops: List[ShipmentPlanPickupStop],
        destination_loc: Location,
        routing_provider: BaseRoutingProvider,
        vehicle_capacity_quintals: Optional[Decimal] = None,
        delivery_deadline: Optional[date] = None,
    ) -> OptimizationExecutionResult:
        if len(stops) <= 1:
            return OptimizationExecutionResult(
                success=True,
                status="OPTIMIZED_ROUTE_FOUND",
                ordered_stops=stops,
                solver_name=self.optimizer_name,
            )

        all_have_gps = all(
            s.pickup_location and s.pickup_location.latitude is not None and s.pickup_location.longitude is not None
            for s in stops
        )

        if not all_have_gps:
            return OptimizationExecutionResult(
                success=True,
                status="OPTIMIZED_ROUTE_FOUND",
                ordered_stops=sorted(stops, key=lambda s: s.stop_sequence),
                solver_name=self.optimizer_name,
            )

        # Nearest Neighbor baseline
        ordered: List[ShipmentPlanPickupStop] = []
        remaining = list(sorted(stops, key=lambda s: s.stop_sequence))
        current = remaining.pop(0)
        ordered.append(current)

        while remaining:
            curr_lat = float(current.pickup_location.latitude)
            curr_lon = float(current.pickup_location.longitude)

            def dist_to_current(s: ShipmentPlanPickupStop) -> float:
                s_lat = float(s.pickup_location.latitude)
                s_lon = float(s.pickup_location.longitude)
                return math.hypot(s_lat - curr_lat, s_lon - curr_lon)

            remaining.sort(key=dist_to_current)
            current = remaining.pop(0)
            ordered.append(current)

        return OptimizationExecutionResult(
            success=True,
            status="OPTIMIZED_ROUTE_FOUND",
            ordered_stops=ordered,
            solver_name=self.optimizer_name,
        )


class ORToolsVehicleRoutingOptimizer(BaseRouteOptimizer):
    """
    Google OR-Tools Constraint Programming / Vehicle Routing Problem solver.
    Solves single-vehicle multi-pickup capacitated routing with fixed destination.
    """

    def __init__(self, time_limit_seconds: int = 5) -> None:
        self.time_limit_seconds = time_limit_seconds

    @property
    def optimizer_name(self) -> str:
        return "Google OR-Tools VRP (Guided Local Search)"

    def optimize(
        self,
        stops: List[ShipmentPlanPickupStop],
        destination_loc: Location,
        routing_provider: BaseRoutingProvider,
        vehicle_capacity_quintals: Optional[Decimal] = None,
        delivery_deadline: Optional[date] = None,
    ) -> OptimizationExecutionResult:
        if len(stops) <= 1:
            return OptimizationExecutionResult(
                success=True,
                status="OPTIMIZED_ROUTE_FOUND",
                ordered_stops=stops,
                solver_name=self.optimizer_name,
            )

        # 1. Prepare coordinate nodes:
        # Node 0..N-1: Pickup Stops
        # Node N: Destination Location
        num_pickups = len(stops)
        num_nodes = num_pickups + 1
        dest_node_idx = num_pickups

        coords: List[LocationCoordinate] = []
        demands_kg: List[int] = []

        for idx, s in enumerate(stops):
            loc = s.pickup_location
            coords.append(
                LocationCoordinate(
                    label=loc.name if loc else f"Pickup {idx+1}",
                    latitude=float(loc.latitude) if loc and loc.latitude is not None else None,
                    longitude=float(loc.longitude) if loc and loc.longitude is not None else None,
                    district=loc.district if loc else None,
                    taluka=loc.taluka if loc else None,
                )
            )
            # 1 quintal = 100 kg
            demands_kg.append(int(round(float(s.allocated_quantity_quintals) * 100.0)))

        # Destination node
        coords.append(
            LocationCoordinate(
                label=destination_loc.name,
                latitude=float(destination_loc.latitude) if destination_loc.latitude is not None else None,
                longitude=float(destination_loc.longitude) if destination_loc.longitude is not None else None,
                district=destination_loc.district,
                taluka=destination_loc.taluka,
            )
        )
        demands_kg.append(0)  # Destination demand is 0

        # 2. Compute full distance matrix (in integer meters)
        matrix_result = routing_provider.get_distance_matrix(coords, coords)
        distance_matrix_meters: List[List[int]] = []
        for row in matrix_result:
            dist_row: List[int] = []
            for val in row:
                if val is not None:
                    dist_row.append(int(round(float(val) * 1000.0)))
                else:
                    dist_row.append(99999999)  # Large penalty for unresolvable path
            distance_matrix_meters.append(dist_row)

        # 3. Setup OR-Tools Routing Model
        # Start at node 0 (first harvest consolidation), end at dest_node_idx (destination)
        manager = pywrapcp.RoutingIndexManager(num_nodes, 1, [0], [dest_node_idx])
        routing = pywrapcp.RoutingModel(manager)

        # Distance Callback
        def distance_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix_meters[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Capacity Dimension
        if vehicle_capacity_quintals is not None and vehicle_capacity_quintals > Decimal("0.0"):
            max_capacity_kg = int(round(float(vehicle_capacity_quintals) * 100.0))

            def demand_callback(from_index: int) -> int:
                from_node = manager.IndexToNode(from_index)
                return demands_kg[from_node]

            demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
            routing.AddDimensionWithVehicleCapacity(
                demand_callback_index,
                0,  # null capacity slack
                [max_capacity_kg],  # vehicle maximum capacities
                True,  # start cumul to zero
                "Capacity",
            )

        # 4. Search Parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = self.time_limit_seconds

        # 5. Solve
        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            # Check if total demand exceeded vehicle capacity
            total_demand_qtl = sum((s.allocated_quantity_quintals for s in stops), Decimal("0.0"))
            if vehicle_capacity_quintals is not None and total_demand_qtl > vehicle_capacity_quintals:
                return OptimizationExecutionResult(
                    success=False,
                    status="CAPACITY_CONSTRAINT_FAILURE",
                    ordered_stops=stops,
                    error_message=f"Total cargo ({total_demand_qtl} qtl) exceeds vehicle capacity ({vehicle_capacity_quintals} qtl).",
                    solver_name=self.optimizer_name,
                )
            return OptimizationExecutionResult(
                success=False,
                status="OPTIMIZATION_INFEASIBLE",
                ordered_stops=stops,
                error_message="OR-Tools solver could not find a feasible routing sequence satisfying all constraints.",
                solver_name=self.optimizer_name,
            )

        # 6. Extract Solution Route
        index = routing.Start(0)
        ordered_stops: List[ShipmentPlanPickupStop] = []

        while not routing.IsEnd(index):
            node_idx = manager.IndexToNode(index)
            if node_idx < num_pickups:
                ordered_stops.append(stops[node_idx])
            index = solution.Value(routing.NextVar(index))

        # Verification: all pickup stops must be present
        if len(ordered_stops) != len(stops):
            return OptimizationExecutionResult(
                success=False,
                status="OPTIMIZATION_INFEASIBLE",
                ordered_stops=stops,
                error_message="Optimized route did not include all required pickup stops.",
                solver_name=self.optimizer_name,
            )

        return OptimizationExecutionResult(
            success=True,
            status="OPTIMIZED_ROUTE_FOUND",
            ordered_stops=ordered_stops,
            solver_name=self.optimizer_name,
        )
