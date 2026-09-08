"""
Phase 2D - Step 3: Deterministic Transport Cost Engine.
Calculates road distance, vehicle payload sizing, fare components, and reefer surcharges.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from app.models.entities import VehicleTypeEnum


@dataclass
class TransportCostBreakdown:
    distance_km: Decimal
    vehicle_type: VehicleTypeEnum
    base_fare: Decimal
    distance_charge: Decimal
    reefer_surcharge: Decimal
    loading_unloading_charge: Decimal
    total_transport_cost: Decimal
    cost_per_quintal: Decimal
    cost_certainty: str  # "VERIFIED_TRANSPORTER_QUOTE", "MODELED_REGIONAL_ESTIMATE", "UNAVAILABLE"
    is_verified_quote: bool
    rate_source: str
    provider_name: Optional[str]
    disclaimer: str
    explanation: str



# Baseline verified regional Maharashtra rate cards (fallback when provider rate card is not in DB)
DEFAULT_RATE_CARDS: Dict[VehicleTypeEnum, Dict[str, Decimal]] = {
    VehicleTypeEnum.MINI_TRUCK: {
        "max_payload_quintals": Decimal("10.0"),  # 1 MT (e.g. Tata Ace)
        "base_fare": Decimal("600.00"),
        "per_km_rate": Decimal("18.00"),
        "min_distance_km": Decimal("10.0"),
        "reefer_surcharge_per_km": Decimal("0.00"),
        "loading_unloading_charge": Decimal("250.00"),
    },
    VehicleTypeEnum.PICKUP: {
        "max_payload_quintals": Decimal("30.0"),  # 3 MT (e.g. Bolero Maxi Truck)
        "base_fare": Decimal("1000.00"),
        "per_km_rate": Decimal("25.00"),
        "min_distance_km": Decimal("15.0"),
        "reefer_surcharge_per_km": Decimal("0.00"),
        "loading_unloading_charge": Decimal("400.00"),
    },
    VehicleTypeEnum.MEDIUM_COMMERCIAL: {
        "max_payload_quintals": Decimal("80.0"),  # 8 MT (e.g. Eicher 6-wheeler)
        "base_fare": Decimal("2200.00"),
        "per_km_rate": Decimal("42.00"),
        "min_distance_km": Decimal("25.0"),
        "reefer_surcharge_per_km": Decimal("10.00"),
        "loading_unloading_charge": Decimal("800.00"),
    },
    VehicleTypeEnum.HEAVY_TRUCK: {
        "max_payload_quintals": Decimal("250.0"),  # 25 MT (e.g. 10/12-wheeler truck)
        "base_fare": Decimal("4500.00"),
        "per_km_rate": Decimal("75.00"),
        "min_distance_km": Decimal("50.0"),
        "reefer_surcharge_per_km": Decimal("18.00"),
        "loading_unloading_charge": Decimal("1500.00"),
    },
    VehicleTypeEnum.REEFER_VAN: {
        "max_payload_quintals": Decimal("40.0"),  # 4 MT Dedicated Reefer
        "base_fare": Decimal("2500.00"),
        "per_km_rate": Decimal("48.00"),
        "min_distance_km": Decimal("20.0"),
        "reefer_surcharge_per_km": Decimal("15.00"),
        "loading_unloading_charge": Decimal("600.00"),
    },
}


def calculate_haversine_road_distance(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, road_factor: float = 1.25
) -> Decimal:
    """
    Computes road distance approximation (Haversine distance multiplied by terrain/road routing factor 1.25).
    """
    R = 6371.0  # Earth radius in km
    d_lat = math.radians(dest_lat - origin_lat)
    d_lon = math.radians(dest_lon - origin_lon)
    lat1 = math.radians(origin_lat)
    lat2 = math.radians(dest_lat)

    a = math.sin(d_lat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    direct_km = R * c
    road_km = direct_km * road_factor

    return Decimal(str(round(max(road_km, 1.0), 2)))


def select_optimal_vehicle_type(quantity_quintals: Decimal, is_perishable: bool = False) -> VehicleTypeEnum:
    """Selects the smallest vehicle type capable of carrying the payload."""
    if is_perishable and quantity_quintals > Decimal("10.0") and quantity_quintals <= Decimal("40.0"):
        return VehicleTypeEnum.REEFER_VAN
    if quantity_quintals <= Decimal("10.0"):
        return VehicleTypeEnum.MINI_TRUCK
    elif quantity_quintals <= Decimal("30.0"):
        return VehicleTypeEnum.PICKUP
    elif quantity_quintals <= Decimal("80.0"):
        return VehicleTypeEnum.MEDIUM_COMMERCIAL
    else:
        return VehicleTypeEnum.HEAVY_TRUCK


def calculate_transport_cost(
    distance_km: Decimal,
    quantity_quintals: Decimal,
    is_perishable: bool = False,
    custom_rate_card: Optional[Dict[str, Any]] = None,
    origin_name: str = "Origin",
    destination_name: str = "Destination",
) -> TransportCostBreakdown:
    """
    Calculates deterministic transport fare and itemized deductions.
    Formula: Fare = max(Distance, Min_Distance) * (Per_KM_Rate + Reefer_Surcharge) + Base_Fare + Loading_Unloading
    """
    v_type = select_optimal_vehicle_type(quantity_quintals, is_perishable=is_perishable)
    card = custom_rate_card or DEFAULT_RATE_CARDS[v_type]
    is_est = custom_rate_card is None

    base_fare = Decimal(str(card["base_fare"]))
    per_km_rate = Decimal(str(card["per_km_rate"]))
    min_dist = Decimal(str(card["min_distance_km"]))
    reefer_surcharge_km = Decimal(str(card.get("reefer_surcharge_per_km", 0))) if is_perishable else Decimal("0.00")
    handling = Decimal(str(card.get("loading_unloading_charge", 0)))

    billable_distance = max(distance_km, min_dist)
    distance_charge = billable_distance * per_km_rate
    reefer_charge = billable_distance * reefer_surcharge_km

    total_cost = base_fare + distance_charge + reefer_charge + handling
    total_cost = Decimal(str(round(total_cost, 2)))

    safe_q = max(quantity_quintals, Decimal("0.01"))
    cost_per_qtl = Decimal(str(round(total_cost / safe_q, 2)))

    explanation = (
        f"Transport by {v_type.value.replace('_', ' ').title()} over {distance_km} km "
        f"({origin_name} → {destination_name}): Base ₹{base_fare} + Distance ₹{distance_charge} "
        f"(@₹{per_km_rate}/km)"
    )
    if is_perishable and reefer_charge > 0:
        explanation += f" + Cold Chain Surcharge ₹{reefer_charge}"
    explanation += f" + Loading/Unloading ₹{handling} = Total ₹{total_cost} (₹{cost_per_qtl}/qtl)"

    is_verified = custom_rate_card is not None
    certainty = "VERIFIED_TRANSPORTER_QUOTE" if is_verified else "MODELED_REGIONAL_ESTIMATE"
    provider = custom_rate_card.get("provider_name") if custom_rate_card else None
    
    if is_verified:
        disclaimer = "Transport rate is verified from an active registered logistics provider rate card on the platform."
        rate_src = f"Verified Transporter Rate Card ({provider or 'Platform Provider'})"
    else:
        disclaimer = "No active verified transporter quote found in database for this route. Transport cost is a modeled regional estimate and must be confirmed prior to shipment dispatch."
        rate_src = "Maharashtra Regional Benchmark Model (No Active Live Transporter Quote)"

    return TransportCostBreakdown(
        distance_km=distance_km,
        vehicle_type=v_type,
        base_fare=base_fare,
        distance_charge=distance_charge,
        reefer_surcharge=reefer_charge,
        loading_unloading_charge=handling,
        total_transport_cost=total_cost,
        cost_per_quintal=cost_per_qtl,
        cost_certainty=certainty,
        is_verified_quote=is_verified,
        rate_source=rate_src,
        provider_name=provider,
        disclaimer=disclaimer,
        explanation=explanation,
    )

