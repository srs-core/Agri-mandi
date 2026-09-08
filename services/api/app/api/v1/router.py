from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    buyer_requirements,
    commodities,
    health,
    intelligence,
    logistics,
    notifications,
    offers,
    orders,
    produce_lots,
    profiles,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(commodities.router)
api_router.include_router(profiles.router)
api_router.include_router(produce_lots.router)
api_router.include_router(buyer_requirements.router)
api_router.include_router(offers.router)
api_router.include_router(orders.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)
api_router.include_router(intelligence.router)
api_router.include_router(logistics.router)
