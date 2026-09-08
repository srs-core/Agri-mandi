"""
Phase 2D: Intelligent Decision Engine.
Orchestrates Buyer Matching, Phase 2C Price Forecasting, Deterministic Transport Costing,
Net Realization calculation, multi-criteria ranking, and transparent explainability.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Commodity, Location, MarketPriceRecord
from app.modules.intelligence.buyer_matching import (
    MatchedBuyerCandidate,
    match_buyers_for_produce,
)
from app.modules.intelligence.forecast_service import forecast_engine
from app.modules.intelligence.transport_cost import (
    TransportCostBreakdown,
    calculate_transport_cost,
)
from app.schemas.intelligence import (
    BuyerRecommendationRequest,
    BuyerRecommendationResponse,
    EconomicOptionBreakdown,
    ForecastPriceReference,
    LogisticsDeductionBreakdown,
    PriceForecastRequest,
)

logger = logging.getLogger(__name__)


# Default reference prices when historical record is not in DB
DEFAULT_COMMODITY_PRICES = {
    "Potato": Decimal("1800.00"),
    "Potato (Jyoti)": Decimal("1800.00"),
    "Onion": Decimal("2200.00"),
    "Onion (Nashik Red)": Decimal("2200.00"),
    "Tomato": Decimal("1600.00"),
    "Tomato (Hybrid)": Decimal("1600.00"),
    "Wheat": Decimal("2400.00"),
    "Wheat (Sharbati)": Decimal("2400.00"),
    "Soybean": Decimal("4600.00"),
    "Pomegranate": Decimal("8500.00"),
}


def resolve_commodity_pricing_and_forecast(
    db: Session,
    commodity: Commodity,
    market_name: str = "Pune APMC (Gultekdi)",
    ref_date: Optional[date] = None,
) -> Tuple[Decimal, str, Optional[ForecastPriceReference]]:
    """
    Retrieves expected unit selling price and ML forecast reference.
    - Potato (Jyoti) & Onion (Nashik Red): Uses approved Phase 2C Next-Day (t+1) ML forecast.
    - Other commodities: Uses latest Agmarknet modal price and explicitly marks forecast as unavailable.
    """
    c_date = ref_date or date.today()
    c_name = commodity.name

    # Check if eligible for Phase 2C approved t+1 forecast
    is_forecast_approved = c_name in ["Potato (Jyoti)", "Potato", "Onion (Nashik Red)", "Onion"]

    if is_forecast_approved:
        std_crop = "Potato (Jyoti)" if "Potato" in c_name else "Onion (Nashik Red)"
        forecast_req = PriceForecastRequest(
            commodity=std_crop,
            market=market_name,
            horizon="t+1",
            reference_date=c_date,
        )
        f_resp = forecast_engine.forecast_price(forecast_req)

        if f_resp.status == "SUCCESS" and f_resp.predicted_modal_price is not None:
            forecast_ref = ForecastPriceReference(
                is_forecast_available=True,
                forecast_horizon="t+1 (Next-Day)",
                predicted_price_per_quintal=f_resp.predicted_modal_price,
                interval_lower_bound=f_resp.empirical_prediction_interval.lower_bound
                if f_resp.empirical_prediction_interval
                else None,
                interval_upper_bound=f_resp.empirical_prediction_interval.upper_bound
                if f_resp.empirical_prediction_interval
                else None,
                interval_coverage_pct=f_resp.empirical_prediction_interval.historical_test_coverage_pct
                if f_resp.empirical_prediction_interval
                else 80.0,
                model_version=f_resp.model_version,
                pricing_source="Approved Phase 2C Next-Day XGBoost Forecast",
            )
            return f_resp.predicted_modal_price, "Approved Next-Day ML Price Forecast", forecast_ref

    # For other crops: Fetch latest modal price from DB
    latest_rec = db.scalar(
        select(MarketPriceRecord)
        .where(MarketPriceRecord.commodity_id == commodity.id)
        .order_by(MarketPriceRecord.price_date.desc())
    )

    if latest_rec and latest_rec.modal_price:
        base_price = latest_rec.modal_price
        source_desc = f"Latest Observed Mandi Auction Modal Price ({latest_rec.price_date})"
    else:
        base_price = DEFAULT_COMMODITY_PRICES.get(c_name, Decimal("2000.00"))
        source_desc = "Regional Benchmark Market Modal Price"

    forecast_ref = ForecastPriceReference(
        is_forecast_available=False,
        forecast_horizon=None,
        predicted_price_per_quintal=None,
        interval_lower_bound=None,
        interval_upper_bound=None,
        interval_coverage_pct=None,
        model_version="offline_only",
        pricing_source=source_desc,
    )

    return base_price, source_desc, forecast_ref


def build_recommendation_reasoning(
    candidate: MatchedBuyerCandidate,
    gross_val: Decimal,
    logistics: TransportCostBreakdown,
    net_val: Decimal,
    net_unit: Decimal,
    unit_price: Decimal,
    price_source: str,
    is_forecast: bool = False,
    is_best: bool = False,
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Generates structured explainability categorized into:
    1. Verified Database Facts
    2. Modeled Economic Estimates
    3. Uncertainties & Cautions
    4. Combined Farmer-Facing Checklist
    """
    facts: List[str] = []
    estimates: List[str] = []
    cautions: List[str] = []
    checklist: List[str] = []

    # 1. Verified Facts
    if candidate.match_type == "EXACT_COMMODITY":
        facts.append(f"✓ Exact commodity match for '{candidate.matched_commodity_name}'")
    else:
        facts.append(f"✓ Broad category buyer match for '{candidate.matched_commodity_name}'")

    facts.append(f"✓ Quantity Check: {candidate.quantity_reason}")
    facts.append(f"✓ Quality Check: {candidate.quality_reason}")
    facts.append(f"✓ Feasible Distance: {candidate.road_distance_km} km ({candidate.geographic_reason})")

    if candidate.is_platform_registered:
        facts.append("✓ Buyer Status: Registered active buyer profile on AgriMandi platform.")
    if candidate.payment_terms:
        facts.append(f"✓ Payment Terms: {candidate.payment_terms}")

    # 2. Modeled Estimates
    if is_forecast:
        estimates.append(f"ℹ Unit Price: ₹{unit_price:,.2f}/qtl based on {price_source}")
    else:
        estimates.append(f"ℹ Unit Price: ₹{unit_price:,.2f}/qtl based on {price_source}")

    if logistics.is_verified_quote:
        facts.append(f"✓ Transport Fare: ₹{logistics.total_transport_cost:,.2f} verified via live transporter rate card")
    else:
        estimates.append(
            f"ℹ Transport Deduction: ₹{logistics.total_transport_cost:,.2f} (₹{logistics.cost_per_quintal:,.2f}/qtl) "
            f"modeled via Maharashtra Regional Benchmark"
        )

    estimates.append(
        f"ℹ Net Realization: ₹{net_val:,.2f} (₹{net_unit:,.2f}/qtl) = Gross ₹{gross_val:,.2f} - Transport ₹{logistics.total_transport_cost:,.2f}"
    )

    # 3. Uncertainties and Cautions
    if not candidate.is_platform_registered:
        cautions.append("⚠ Buyer Status: Researched directory record from Phase 2A offline survey; buyer has not yet registered on platform.")
    if not logistics.is_verified_quote:
        cautions.append("⚠ Logistics Quote: Transport cost is a modeled regional estimate; no live verified transporter quote exists on platform.")
    if is_forecast:
        cautions.append("⚠ Market Volatility: Price is an empirical ML forecast; live daily auction prices may vary with supply arrivals.")

    # 4. Combined Checklist
    if is_best:
        checklist.append(
            f"★ BEST ECONOMIC OPTION: Maximizes expected net realization at ₹{net_val:,.2f} (₹{net_unit:,.2f}/qtl)."
        )
    checklist.extend(facts)
    checklist.extend(estimates)
    checklist.extend(cautions)

    return facts, estimates, cautions, checklist



def evaluate_produce_decision(
    db: Session,
    request: BuyerRecommendationRequest,
) -> BuyerRecommendationResponse:
    """
    Executes end-to-end multi-criteria decision engine:
    1. Matches candidates
    2. Incorporates price / approved t+1 forecasts
    3. Calculates deterministic logistics
    4. Computes net realizations
    5. Ranks and generates explainable checklists or safe fallbacks
    """
    # 1. Resolve Commodity & Location
    commodity = db.scalar(
        select(Commodity).where(
            (Commodity.id == request.commodity_id)
            if request.commodity_id
            else (Commodity.name.ilike(f"%{request.commodity_name}%"))
        )
    )
    if not commodity:
        # Fallback for unknown commodity
        return BuyerRecommendationResponse(
            status="NO_ELIGIBLE_BUYER_MATCH",
            commodity_name=request.commodity_name or "Unknown Commodity",
            quantity_quintals=request.quantity_quintals,
            quality_grade=request.quality_grade,
            pickup_location_name="Unknown Location",
            recommended_option=None,
            alternative_options=[],
            forecast_reference=ForecastPriceReference(
                is_forecast_available=False,
                pricing_source="None",
                model_version="none"
            ),
            fallback_reason="Commodity not recognized or not active in platform catalog.",
            explanation=["No active buyers or market price records found for this crop in catalog."]
        )

    pickup_loc = None
    if request.pickup_location_id:
        pickup_loc = db.scalar(select(Location).where(Location.id == request.pickup_location_id))

    pickup_name = (
        pickup_loc.name
        if pickup_loc
        else (request.pickup_location_name or "Pune Rural / Farm Gate")
    )

    # 2. Get Price & Forecast Reference
    base_unit_price, price_source, forecast_ref = resolve_commodity_pricing_and_forecast(
        db, commodity, ref_date=request.availability_date
    )

    # 3. Match Buyers
    candidates = match_buyers_for_produce(
        db=db,
        commodity_id=commodity.id,
        quantity_quintals=request.quantity_quintals,
        quality_grade=request.quality_grade,
        pickup_location=pickup_loc,
        availability_date=request.availability_date,
    )

    if not candidates:
        # Safe fallback when zero buyers exist
        return BuyerRecommendationResponse(
            status="NO_ELIGIBLE_BUYER_MATCH",
            commodity_name=commodity.name,
            quantity_quintals=request.quantity_quintals,
            quality_grade=request.quality_grade,
            pickup_location_name=pickup_name,
            recommended_option=None,
            alternative_options=[],
            forecast_reference=forecast_ref,
            fallback_reason=f"No active buyers or purchase requirements currently found for {commodity.name}.",
            explanation=[
                f"No verified buyers or active purchase requirements found in database for '{commodity.name}'.",
                f"Market Reference Benchmark: ₹{base_unit_price:,.2f}/quintal ({price_source}).",
                "Recommendation: Publish produce lot to open marketplace for registered FPOs/aggregators."
            ]
        )

    # 4. Economic Evaluation for each candidate
    option_list: List[EconomicOptionBreakdown] = []

    is_forecast_used = forecast_ref.is_forecast_available

    for cand in candidates:
        # Unit price: Buyer target price if specified, else market/forecast price
        unit_price = cand.buyer_target_price_per_unit or base_unit_price
        p_src = "Buyer Bid Price" if cand.buyer_target_price_per_unit else price_source

        gross_value = request.quantity_quintals * unit_price

        # Logistics
        logistics = calculate_transport_cost(
            distance_km=cand.road_distance_km,
            quantity_quintals=request.quantity_quintals,
            is_perishable=commodity.is_perishable,
            origin_name=pickup_name,
            destination_name=cand.destination_location_name,
        )

        net_realization = gross_value - logistics.total_transport_cost
        net_per_unit = round(net_realization / max(request.quantity_quintals, Decimal("0.01")), 2)

        is_economically_viable = net_realization > Decimal("0.00") and cand.is_eligible

        facts, estimates, cautions, reasons = build_recommendation_reasoning(
            candidate=cand,
            gross_val=gross_value,
            logistics=logistics,
            net_val=net_realization,
            net_unit=net_per_unit,
            unit_price=unit_price,
            price_source=p_src,
            is_forecast=is_forecast_used,
            is_best=False,
        )

        logistics_schema = LogisticsDeductionBreakdown(
            distance_km=logistics.distance_km,
            vehicle_type=logistics.vehicle_type.value,
            base_fare=logistics.base_fare,
            distance_charge=logistics.distance_charge,
            reefer_surcharge=logistics.reefer_surcharge,
            loading_unloading_charge=logistics.loading_unloading_charge,
            total_transport_cost=logistics.total_transport_cost,
            cost_per_quintal=logistics.cost_per_quintal,
            cost_certainty=logistics.cost_certainty,
            is_verified_quote=logistics.is_verified_quote,
            rate_source=logistics.rate_source,
            provider_name=logistics.provider_name,
            disclaimer=logistics.disclaimer,
            explanation=logistics.explanation,
        )

        is_net_est = (not logistics.is_verified_quote) or is_forecast_used or (not cand.is_platform_registered)
        net_cert = "VERIFIED_QUOTE" if (cand.is_platform_registered and logistics.is_verified_quote and not is_forecast_used) else "CONDITIONAL_ESTIMATE"

        option_list.append(
            EconomicOptionBreakdown(
                buyer_id=cand.buyer_id,
                business_name=cand.business_name,
                buyer_type=cand.buyer_type,
                source_type=cand.source_type,
                buyer_provenance=cand.buyer_provenance,
                is_platform_registered=cand.is_platform_registered,
                destination_name=cand.destination_location_name,
                destination_district=cand.destination_district,
                road_distance_km=cand.road_distance_km,
                expected_unit_price=unit_price,
                pricing_source=p_src,
                gross_selling_value=gross_value,
                logistics_deduction=logistics_schema,
                expected_net_realization=net_realization,
                net_realization_per_quintal=net_per_unit,
                net_realization_certainty=net_cert,
                is_net_realization_estimated=is_net_est,
                match_score=cand.match_score,
                is_eligible=cand.is_eligible,
                is_economically_viable=is_economically_viable,
                verified_facts=facts,
                modeled_estimates=estimates,
                uncertainties_and_cautions=cautions,
                reasoning_checklist=reasons,
            )
        )

    # 5. Rank Options: Eligible with highest net realization first
    eligible_options = [o for o in option_list if o.is_economically_viable]
    ineligible_options = [o for o in option_list if not o.is_economically_viable]

    eligible_options.sort(
        key=lambda x: (x.expected_net_realization, x.is_platform_registered, x.match_score), reverse=True
    )


    if not eligible_options:
        # All candidates violated constraints or resulted in negative net realization
        return BuyerRecommendationResponse(
            status="NO_ELIGIBLE_BUYER_MATCH",
            commodity_name=commodity.name,
            quantity_quintals=request.quantity_quintals,
            quality_grade=request.quality_grade,
            pickup_location_name=pickup_name,
            recommended_option=None,
            alternative_options=ineligible_options[:3],
            forecast_reference=forecast_ref,
            fallback_reason="Available buyers exceeded procurement radius or failed quality/quantity compatibility.",
            explanation=[
                "All matched buyers in directory exceeded maximum procurement range or minimum quality constraints.",
                f"Reference modal price: ₹{base_unit_price:,.2f}/quintal ({price_source}).",
                "Recommendation: Adjust quantity or explore local APMC mandi aggregator channels."
            ]
        )

    # Best Option
    best_opt = eligible_options[0]
    best_opt.reasoning_checklist.insert(
        0,
        f"★ BEST ECONOMIC OPTION: Maximizes farmer net realization at ₹{best_opt.expected_net_realization:,.2f} "
        f"(₹{best_opt.net_realization_per_quintal:,.2f}/quintal)."
    )

    alternatives = eligible_options[1:4]

    return BuyerRecommendationResponse(
        status="SUCCESS",
        commodity_name=commodity.name,
        quantity_quintals=request.quantity_quintals,
        quality_grade=request.quality_grade,
        pickup_location_name=pickup_name,
        recommended_option=best_opt,
        alternative_options=alternatives,
        forecast_reference=forecast_ref,
        fallback_reason=None,
        explanation=[
            f"Evaluated {len(option_list)} potential buyers ({len(eligible_options)} eligible, {len(ineligible_options)} constraint violations).",
            f"Recommended: {best_opt.business_name} ({best_opt.destination_name}) providing highest net realization ₹{best_opt.expected_net_realization:,.2f}.",
            f"Logistics Deductions: ₹{best_opt.logistics_deduction.total_transport_cost:,.2f} ({best_opt.logistics_deduction.vehicle_type} over {best_opt.road_distance_km} km)."
        ]
    )
