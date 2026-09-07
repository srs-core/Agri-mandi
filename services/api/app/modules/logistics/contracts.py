from __future__ import annotations

from typing import Protocol
from uuid import UUID


class LogisticsPlanningService(Protocol):
    """Future boundary for providers, vehicles, storage, routes, jobs, GPS, ETA and assignment."""

    def plan_for_order(self, order_id: UUID) -> object: ...
