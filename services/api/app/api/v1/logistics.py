from __future__ import annotations

from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import ShipmentPlanningStatus, StorageType
from app.modules.logistics.service import (
    create_collection_centre,
    create_historical_infrastructure_record,
    create_logistics_provider,
    create_shipment,
    create_storage_facility,
    list_collection_centres,
    list_historical_infrastructure_records,
    list_logistics_providers,
    list_storage_facilities,
    record_shipment_event,
)
from app.modules.logistics.shipment_planning_service import (
    cancel_shipment_plan,
    create_shipment_plan_from_order,
    create_shipment_plan_from_requirement,
    get_shipment_plan,
    list_shipment_plans,
    mark_shipment_plan_ready,
)
from app.schemas.logistics import (
    CollectionCentreCreate,
    CollectionCentreResponse,
    HistoricalInfrastructureRecordCreate,
    HistoricalInfrastructureRecordResponse,
    LogisticsProviderCreate,
    LogisticsProviderResponse,
    ShipmentCreate,
    ShipmentEventCreate,
    ShipmentEventResponse,
    ShipmentResponse,
    StorageFacilityCreate,
    StorageFacilityResponse,
)
from app.modules.logistics.route_planning_engine import (
    build_and_evaluate_route_plan,
    optimize_shipment_plan_route,
)
from app.modules.logistics.vehicle_feasibility_engine import (
    evaluate_direct_vehicle_feasibility,
    evaluate_shipment_plan_vehicle_feasibility,
)
from app.schemas.route_optimization import RouteOptimizationResponse
from app.schemas.route_planning import RoutePlanResponse

from app.schemas.shipment_plan import (
    ShipmentPlanFromOrderRequest,
    ShipmentPlanFromRequirementRequest,
    ShipmentPlanListResponse,
    ShipmentPlanResponse,
)
from app.schemas.vehicle_feasibility import (
    DirectVehicleFeasibilityRequest,
    ShipmentVehicleFeasibilityResponse,
)

from app.modules.logistics.execution_bridge_service import (
    assemble_logistics_cost_summary,
    assess_logistics_readiness,
    create_shipment_from_plan,
)
from app.schemas.execution_bridge import (
    CreateShipmentFromPlanRequest,
    LogisticsCostSummary,
    LogisticsReadinessAssessment,
)

router = APIRouter(prefix="/logistics", tags=["logistics"])


# ==========================================
# PHASE 2A: DISCOVERY & INFRASTRUCTURE ROUTES
# ==========================================

@router.get("/providers", response_model=list[LogisticsProviderResponse], summary="List registered/researched logistics providers")
def get_logistics_providers(
    db: Annotated[Session, Depends(get_db)],
    has_cold_chain: bool | None = None,
    operating_scope: str | None = None,
) -> list[LogisticsProviderResponse]:
    return list_logistics_providers(db, has_cold_chain=has_cold_chain, operating_scope=operating_scope)


@router.post("/providers", response_model=LogisticsProviderResponse, summary="Register logistics provider")
def post_logistics_provider(
    payload: LogisticsProviderCreate,
    db: Annotated[Session, Depends(get_db)],
) -> LogisticsProviderResponse:
    return create_logistics_provider(db, payload)


@router.get("/storage-facilities", response_model=list[StorageFacilityResponse], summary="List storage facilities (cold stores / godowns)")
def get_storage_facilities(
    db: Annotated[Session, Depends(get_db)],
    is_cold_chain: bool | None = None,
    facility_type: StorageType | None = None,
    district: str | None = None,
    taluka: str | None = None,
) -> list[StorageFacilityResponse]:
    return list_storage_facilities(db, is_cold_chain=is_cold_chain, facility_type=facility_type, district=district, taluka=taluka)


@router.post("/storage-facilities", response_model=StorageFacilityResponse, summary="Register storage facility")
def post_storage_facility(
    payload: StorageFacilityCreate,
    db: Annotated[Session, Depends(get_db)],
) -> StorageFacilityResponse:
    return create_storage_facility(db, payload)


@router.get("/collection-centres", response_model=list[CollectionCentreResponse], summary="List collection & aggregation packhouses")
def get_collection_centres(
    db: Annotated[Session, Depends(get_db)],
    district: str | None = None,
    taluka: str | None = None,
) -> list[CollectionCentreResponse]:
    return list_collection_centres(db, district=district, taluka=taluka)


@router.post("/collection-centres", response_model=CollectionCentreResponse, summary="Register collection centre")
def post_collection_centre(
    payload: CollectionCentreCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CollectionCentreResponse:
    return create_collection_centre(db, payload)


@router.get("/historical-infrastructure", response_model=list[HistoricalInfrastructureRecordResponse], summary="List historical cold-chain project evidence")
def get_historical_infrastructure(
    db: Annotated[Session, Depends(get_db)],
    commodity_sector: str | None = None,
    district_area: str | None = None,
) -> list[HistoricalInfrastructureRecordResponse]:
    return list_historical_infrastructure_records(db, commodity_sector=commodity_sector, district_area=district_area)


@router.post("/historical-infrastructure", response_model=HistoricalInfrastructureRecordResponse, summary="Record historical infrastructure evidence")
def post_historical_infrastructure(
    payload: HistoricalInfrastructureRecordCreate,
    db: Annotated[Session, Depends(get_db)],
) -> HistoricalInfrastructureRecordResponse:
    return create_historical_infrastructure_record(db, payload)


@router.post("/shipments", response_model=ShipmentResponse, summary="Create operational shipment record")
def post_shipment(
    payload: ShipmentCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentResponse:
    return create_shipment(db, payload)


@router.post("/shipments/{shipment_id}/events", response_model=ShipmentEventResponse, summary="Record shipment tracking event")
def post_shipment_event(
    shipment_id: UUID,
    payload: ShipmentEventCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentEventResponse:
    return record_shipment_event(db, shipment_id, payload)


# ==========================================
# PHASE 2E: SHIPMENT PLANNING ROUTES
# ==========================================

@router.post("/shipments/plan/from-requirement", response_model=ShipmentPlanResponse, summary="Create a structured shipment plan to fulfill a Buyer Requirement")
def post_shipment_plan_from_requirement(
    request: ShipmentPlanFromRequirementRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentPlanResponse:
    return create_shipment_plan_from_requirement(db, request)


@router.post("/shipments/plan/from-order", response_model=ShipmentPlanResponse, summary="Create a structured shipment plan from a confirmed Order")
def post_shipment_plan_from_order(
    request: ShipmentPlanFromOrderRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentPlanResponse:
    return create_shipment_plan_from_order(db, request)


@router.get("/shipments/plans", response_model=ShipmentPlanListResponse, summary="List structured shipment plans")
def get_shipment_plans(
    db: Annotated[Session, Depends(get_db)],
    status: Optional[ShipmentPlanningStatus] = None,
    commodity_id: Optional[UUID] = None,
    buyer_requirement_id: Optional[UUID] = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> ShipmentPlanListResponse:
    return list_shipment_plans(
        db=db,
        status_filter=status,
        commodity_id=commodity_id,
        buyer_requirement_id=buyer_requirement_id,
        limit=limit,
    )


@router.get("/shipments/plans/{plan_id}", response_model=ShipmentPlanResponse, summary="Get details and stops for a specific shipment plan")
def get_shipment_plan_detail(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentPlanResponse:
    return get_shipment_plan(db, plan_id)


@router.post("/shipments/plans/{plan_id}/ready", response_model=ShipmentPlanResponse, summary="Transition shipment plan to READY_FOR_LOGISTICS")
def post_shipment_plan_ready(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentPlanResponse:
    return mark_shipment_plan_ready(db, plan_id)


@router.post("/shipments/plans/{plan_id}/cancel", response_model=ShipmentPlanResponse, summary="Cancel a planned shipment and release allocated produce")
def post_shipment_plan_cancel(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    reason: Optional[str] = Query(default=None, description="Reason for cancellation"),
) -> ShipmentPlanResponse:
    return cancel_shipment_plan(db, plan_id, reason=reason)


# ==========================================
# PHASE 2E: VEHICLE FEASIBILITY & SELECTION
# ==========================================

@router.post(
    "/shipments/{shipment_id}/vehicle-options",
    response_model=ShipmentVehicleFeasibilityResponse,
    summary="Evaluate vehicle sizing feasibility and candidate options for a ShipmentPlan",
)
def post_shipment_vehicle_options(
    shipment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentVehicleFeasibilityResponse:
    return evaluate_shipment_plan_vehicle_feasibility(db, shipment_id)


@router.post(
    "/vehicles/evaluate-feasibility",
    response_model=ShipmentVehicleFeasibilityResponse,
    summary="Evaluate vehicle sizing feasibility on arbitrary cargo/commodity parameters",
)
def post_direct_vehicle_feasibility(
    request: DirectVehicleFeasibilityRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentVehicleFeasibilityResponse:
    return evaluate_direct_vehicle_feasibility(db, request)


# ==========================================
# PHASE 2E: ROUTE PLANNING & WAYPOINTS
# ==========================================

@router.post(
    "/shipments/{shipment_id}/route-plan",
    response_model=RoutePlanResponse,
    summary="Generate or evaluate an ordered waypoint route plan for a ShipmentPlan",
)
def post_shipment_route_plan(
    shipment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> RoutePlanResponse:
    return build_and_evaluate_route_plan(db, shipment_id)


@router.get(
    "/shipments/{shipment_id}/route-plan",
    response_model=RoutePlanResponse,
    summary="Retrieve the route plan and waypoint sequence for a ShipmentPlan",
)
def get_shipment_route_plan(
    shipment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> RoutePlanResponse:
    return build_and_evaluate_route_plan(db, shipment_id)


@router.post(
    "/shipments/{shipment_id}/route-optimize",
    response_model=RouteOptimizationResponse,
    summary="Run Google OR-Tools VRP multi-stop route optimization and compute comparison savings",
)
def post_shipment_route_optimize(
    shipment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> RouteOptimizationResponse:
    return optimize_shipment_plan_route(db, shipment_id)


# ==========================================
# PHASE 2E: LOGISTICS EXECUTION BRIDGE
# ==========================================

@router.get(
    "/shipments/plans/{plan_id}/readiness",
    response_model=LogisticsReadinessAssessment,
    summary="Evaluate comprehensive operational readiness (status, stops, GPS, vehicle, route, cost) for a ShipmentPlan",
)
def get_shipment_plan_readiness(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> LogisticsReadinessAssessment:
    return assess_logistics_readiness(db, plan_id)


@router.get(
    "/shipments/plans/{plan_id}/cost-summary",
    response_model=LogisticsCostSummary,
    summary="Get consolidated, itemized transport cost breakdown for a ShipmentPlan",
)
def get_shipment_plan_cost_summary(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> LogisticsCostSummary:
    return assemble_logistics_cost_summary(db, plan_id)


@router.post(
    "/shipments/plans/{plan_id}/create-shipment",
    response_model=ShipmentResponse,
    status_code=201,
    summary="Convert a READY_FOR_LOGISTICS ShipmentPlan into an operational Shipment record",
)
def post_create_shipment_from_plan(
    plan_id: UUID,
    payload: CreateShipmentFromPlanRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentResponse:
    return create_shipment_from_plan(db, plan_id, payload)


# ==========================================
# PHASE 2G: TRANSPORTER MARKETPLACE & DISPATCH
# ==========================================

from app.models.entities import TransportOpportunityStatus, RoleName
from app.modules.auth.dependencies import CurrentUser, require_roles
from app.modules.logistics.opportunity_engine import generate_opportunities_for_plan
from app.modules.logistics.transporter_service import (
    accept_opportunity_transactional,
    decline_opportunity,
    get_opportunity_detail,
    get_transporter_me,
    list_opportunities_for_transporter,
    list_transporter_shipments,
    list_transporter_vehicles,
    register_transporter_vehicle,
    submit_transporter_quote,
    update_transporter_profile,
    update_transporter_vehicle,
)
from app.schemas.transporter import (
    BroadcastOpportunitiesResponse,
    OpportunityAcceptRequest,
    OpportunityDeclineRequest,
    TransporterMeResponse,
    TransporterProfileResponse,
    TransporterProfileUpdate,
    TransporterQuoteCreate,
    TransporterQuoteResponse,
    TransporterVehicleCreate,
    TransporterVehicleResponse,
    TransporterVehicleUpdate,
    TransportOpportunityDetailResponse,
    TransportOpportunityResponse,
)


@router.get(
    "/transporter/me",
    response_model=TransporterMeResponse,
    summary="Get transporter profile and operational dashboard summary",
)
def get_transporter_dashboard_summary(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransporterMeResponse:
    return get_transporter_me(db, current_user.id)


@router.put(
    "/transporter/profile",
    response_model=TransporterProfileResponse,
    summary="Update transporter profile details, service areas, and contact information",
)
def put_transporter_profile(
    payload: TransporterProfileUpdate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransporterProfileResponse:
    return update_transporter_profile(db, current_user.id, payload)


@router.get(
    "/transporter/vehicles",
    response_model=list[TransporterVehicleResponse],
    summary="List all registered vehicles for the authenticated transporter",
)
def get_transporter_vehicles(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[TransporterVehicleResponse]:
    return list_transporter_vehicles(db, current_user.id)


@router.post(
    "/transporter/vehicles",
    response_model=TransporterVehicleResponse,
    status_code=201,
    summary="Register a new commercial freight vehicle in the transporter's fleet",
)
def post_transporter_vehicle(
    payload: TransporterVehicleCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransporterVehicleResponse:
    return register_transporter_vehicle(db, current_user.id, payload)


@router.patch(
    "/transporter/vehicles/{vehicle_id}",
    response_model=TransporterVehicleResponse,
    summary="Update availability or operational details of a registered vehicle",
)
def patch_transporter_vehicle(
    vehicle_id: UUID,
    payload: TransporterVehicleUpdate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransporterVehicleResponse:
    return update_transporter_vehicle(db, current_user.id, vehicle_id, payload)


@router.get(
    "/transporter/opportunities",
    response_model=list[TransportOpportunityResponse],
    summary="List available transport opportunities matched to the authenticated transporter",
)
def get_transporter_opportunities(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    status: Optional[TransportOpportunityStatus] = None,
) -> list[TransportOpportunityResponse]:
    return list_opportunities_for_transporter(db, current_user.id, status=status)


@router.get(
    "/transporter/opportunities/{opportunity_id}",
    response_model=TransportOpportunityDetailResponse,
    summary="Get full details, stops, waypoints, and vehicle options for a transport opportunity",
)
def get_transporter_opportunity_detail(
    opportunity_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransportOpportunityDetailResponse:
    return get_opportunity_detail(db, current_user.id, opportunity_id)


@router.post(
    "/transporter/opportunities/{opportunity_id}/accept",
    response_model=TransportOpportunityDetailResponse,
    summary="Transactionally accept a transport job, lock vehicle assignment, and schedule shipment",
)
def post_accept_opportunity(
    opportunity_id: UUID,
    payload: OpportunityAcceptRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransportOpportunityDetailResponse:
    return accept_opportunity_transactional(db, current_user.id, opportunity_id, payload)


@router.post(
    "/transporter/opportunities/{opportunity_id}/decline",
    response_model=TransportOpportunityResponse,
    summary="Decline a transport opportunity with an optional reason",
)
def post_decline_opportunity(
    opportunity_id: UUID,
    payload: OpportunityDeclineRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransportOpportunityResponse:
    return decline_opportunity(db, current_user.id, opportunity_id, payload)


@router.post(
    "/transporter/opportunities/{opportunity_id}/quotes",
    response_model=TransporterQuoteResponse,
    status_code=201,
    summary="Submit a verified commercial freight bid or quote for an opportunity",
)
def post_submit_transporter_quote(
    opportunity_id: UUID,
    payload: TransporterQuoteCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransporterQuoteResponse:
    return submit_transporter_quote(db, current_user.id, opportunity_id, payload)


@router.get(
    "/transporter/shipments",
    response_model=list[dict[str, Any]],
    summary="List active, in-transit, or completed shipments assigned to the transporter",
)
def get_transporter_shipments(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    return list_transporter_shipments(db, current_user.id)


@router.post(
    "/shipments/plans/{plan_id}/broadcast-opportunities",
    response_model=BroadcastOpportunitiesResponse,
    summary="Broadcast a ready ShipmentPlan to eligible registered transporters",
)
def post_broadcast_plan_opportunities(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    force_rebroadcast: bool = Query(default=False),
) -> BroadcastOpportunitiesResponse:
    return generate_opportunities_for_plan(db, plan_id, force_rebroadcast=force_rebroadcast)


# ==========================================
# PHASE 2H: SHIPMENT EXECUTION & TRACKING
# ==========================================

from app.modules.logistics.execution_tracking_service import (
    get_shipment_execution_detail,
    record_checkpoint_arrival,
    record_checkpoint_completion,
    record_checkpoint_loading_start,
    record_delivery_completion,
    record_destination_arrival,
    record_transit_start,
    report_shipment_exception,
)
from app.schemas.execution_tracking import (
    CheckpointArriveRequest,
    CheckpointCompleteRequest,
    CheckpointLoadingRequest,
    DeliveryCompleteRequest,
    DestinationArriveRequest,
    ShipmentExceptionRequest,
    ShipmentExecutionDetailResponse,
    TransitStartRequest,
)


@router.get(
    "/shipments/{shipment_id}",
    response_model=ShipmentExecutionDetailResponse,
    summary="Get real-time execution tracking, sequential milestones, and cargo progress for a shipment",
)
def get_shipment_tracking(
    shipment_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentExecutionDetailResponse:
    user_roles = [ur.role.name.value for ur in current_user.user_roles if ur.role is not None]
    return get_shipment_execution_detail(db, current_user.id, user_roles, shipment_id)


@router.get(
    "/shipments/{shipment_id}/events",
    response_model=list[ShipmentEventResponse],
    summary="Get milestone audit timeline events for a shipment",
)
def get_shipment_events(
    shipment_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[ShipmentEventResponse]:
    user_roles = [ur.role.name.value for ur in current_user.user_roles if ur.role is not None]
    detail = get_shipment_execution_detail(db, current_user.id, user_roles, shipment_id)
    return detail.timeline


@router.post(
    "/shipments/{shipment_id}/checkpoints/{checkpoint_id}/arrive",
    response_model=ShipmentExecutionDetailResponse,
    summary="Confirm vehicle arrival at a designated pickup or destination checkpoint",
)
def post_checkpoint_arrival(
    shipment_id: UUID,
    checkpoint_id: UUID,
    payload: CheckpointArriveRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentExecutionDetailResponse:
    return record_checkpoint_arrival(db, current_user.id, shipment_id, checkpoint_id, payload)


@router.post(
    "/shipments/{shipment_id}/checkpoints/{checkpoint_id}/start-loading",
    response_model=ShipmentExecutionDetailResponse,
    summary="Confirm that crop loading has commenced at a pickup checkpoint",
)
def post_checkpoint_loading_start(
    shipment_id: UUID,
    checkpoint_id: UUID,
    payload: CheckpointLoadingRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentExecutionDetailResponse:
    return record_checkpoint_loading_start(db, current_user.id, shipment_id, checkpoint_id, payload)


@router.post(
    "/shipments/{shipment_id}/checkpoints/{checkpoint_id}/complete",
    response_model=ShipmentExecutionDetailResponse,
    summary="Complete a farm pickup stop, verifying loaded cargo quantity and documenting any variances",
)
def post_checkpoint_complete(
    shipment_id: UUID,
    checkpoint_id: UUID,
    payload: CheckpointCompleteRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentExecutionDetailResponse:
    return record_checkpoint_completion(db, current_user.id, shipment_id, checkpoint_id, payload)


@router.post(
    "/shipments/{shipment_id}/transit/start",
    response_model=ShipmentExecutionDetailResponse,
    summary="Confirm departure from final pickup stop and start road linehaul transit",
)
def post_transit_start(
    shipment_id: UUID,
    payload: TransitStartRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentExecutionDetailResponse:
    return record_transit_start(db, current_user.id, shipment_id, payload)


@router.post(
    "/shipments/{shipment_id}/destination/arrive",
    response_model=ShipmentExecutionDetailResponse,
    summary="Confirm arrival at buyer destination hub / receiving terminal",
)
def post_destination_arrival(
    shipment_id: UUID,
    payload: DestinationArriveRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentExecutionDetailResponse:
    return record_destination_arrival(db, current_user.id, shipment_id, payload)


@router.post(
    "/shipments/{shipment_id}/delivery/complete",
    response_model=ShipmentExecutionDetailResponse,
    summary="Confirm delivery completion, receiver sign-off, and release vehicle back to fleet",
)
def post_delivery_complete(
    shipment_id: UUID,
    payload: DeliveryCompleteRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentExecutionDetailResponse:
    return record_delivery_completion(db, current_user.id, shipment_id, payload)


@router.post(
    "/shipments/{shipment_id}/exceptions",
    response_model=ShipmentExecutionDetailResponse,
    summary="Report an operational exception or logistics issue without advancing the checkpoint",
)
def post_shipment_exception(
    shipment_id: UUID,
    payload: ShipmentExceptionRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ShipmentExecutionDetailResponse:
    return report_shipment_exception(db, current_user.id, shipment_id, payload)






