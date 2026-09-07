from uuid import uuid4
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.entities import (
    Commodity,
    Location,
    ShipmentPlan,
    ShipmentPlanPickupStop,
    ShipmentPlanningStatus,
    TransportOpportunity,
    TransportOpportunityStatus,
    TransporterProfile,
    User,
    UserRole,
    Role,
    RoleName,
)

def seed_opportunity():
    db = SessionLocal()
    try:
        # 1. Locations
        pune = db.scalar(select(Location).where(Location.district.ilike("%pune%")))
        if not pune:
            pune = Location(name="Manchar APMC Yard", district="Pune", state="Maharashtra", latitude=19.006, longitude=73.945)
            db.add(pune)
            db.flush()

        nashik = db.scalar(select(Location).where(Location.district.ilike("%nashik%")))
        if not nashik:
            nashik = Location(name="Lasalgaon Mandi Yard", district="Nashik", state="Maharashtra", latitude=20.147, longitude=74.226)
            db.add(nashik)
            db.flush()

        mumbai = db.scalar(select(Location).where(Location.district.ilike("%mumbai%")))
        if not mumbai:
            mumbai = Location(name="APMC Vashi Terminal", district="Mumbai", state="Maharashtra", latitude=19.076, longitude=72.998)
            db.add(mumbai)
            db.flush()

        # 2. Commodity
        comm = db.scalar(select(Commodity).where(Commodity.name.ilike("%potato%")))
        if not comm:
            comm = db.scalar(select(Commodity))
        if not comm:
            comm = Commodity(name="Potato (Jyoti)", category="vegetables", code="POT-JYO")
            db.add(comm)
            db.flush()

        # Farmer user for pickup stops
        farmer = db.scalar(select(User).join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id).where(Role.name == RoleName.FARMER))
        if not farmer:
            farmer = db.scalar(select(User))

        # 3. Shipment Plan
        plan_code = f"PLAN-EXEC-{uuid4().hex[:6].upper()}"
        plan = ShipmentPlan(
            plan_code=plan_code,
            commodity_id=comm.id,
            destination_location_id=mumbai.id,
            planning_status=ShipmentPlanningStatus.PLANNED,
            earliest_pickup_date=date.today(),
            delivery_deadline=date.today() + timedelta(days=2),
            total_planned_quantity_quintals=35.0,
            estimated_gross_merchandise_value=87500.0,
        )
        db.add(plan)
        db.flush()

        stop1 = ShipmentPlanPickupStop(
            shipment_plan_id=plan.id,
            stop_sequence=1,
            seller_user_id=farmer.id,
            seller_name="Ramesh Patil (Manchar Farm)",
            pickup_location_id=pune.id,
            allocated_quantity_quintals=15.0,
            earliest_pickup_date=date.today(),
        )
        stop2 = ShipmentPlanPickupStop(
            shipment_plan_id=plan.id,
            stop_sequence=2,
            seller_user_id=farmer.id,
            seller_name="Suresh Deshmukh (Lasalgaon Farm)",
            pickup_location_id=nashik.id,
            allocated_quantity_quintals=20.0,
            earliest_pickup_date=date.today(),
        )
        db.add_all([stop1, stop2])
        db.commit()

        # 4. Broadcast opportunity using transporter service
        from app.modules.logistics.opportunity_engine import generate_opportunities_for_plan
        bcast = generate_opportunities_for_plan(db, plan.id, force_rebroadcast=True)

        print(f"SEEDED_PLAN_CODE={plan.plan_code}")
        print(f"SEEDED_PLAN_ID={plan.id}")
        print(f"BROADCAST_COUNT={bcast.opportunities_created_count}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_opportunity()
