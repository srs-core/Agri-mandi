from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RecommendationRequest:
    produce_lot_id: UUID


class BuyerRecommendationService(Protocol):
    def rank_buyers(self, request: RecommendationRequest) -> list[object]: ...


class PriceForecastingService(Protocol):
    def forecast_price(self, commodity_id: UUID, location_id: UUID) -> object: ...


class DemandForecastingService(Protocol):
    def forecast_demand(self, commodity_id: UUID, location_id: UUID) -> object: ...


class NetRealizationService(Protocol):
    def calculate(self, gross_amount: Decimal, cost_inputs: object) -> object: ...
