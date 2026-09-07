import sys
import uuid
from decimal import Decimal
from datetime import date, timedelta
from app.db.session import SessionLocal
from app.models.entities import (
    User,
    TransporterProfile,
    ShipmentPlan,
    ShipmentPlanPickupStop,
    Location,
    Commodity,
    ShipmentPlanningStatus,
)
from app.modules.logistics.opportunity_engine import generate_opportunities_for_plan

def main():
    if len(sys.argv) < 2:
        print("Usage: python seed_notif_e2e.py <transporter_email>")
        sys.exit(1)

    email = sys.argv[1]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"User {email} not found")
            sys.exit(1)

        profile = db.query(TransporterProfile).filter(TransporterProfile.user_id == user.id).first()
        if profile:
            profile.service_area_districts = ["Pune", "Mumbai", "Nashik", "Ahmednagar"]
            db.commit()

        commodity = db.query(Commodity).filter(Commodity.name == "Potato (Jyoti)").first()
        dest = db.query(Location).filter(Location.district == "Mumbai").first()
        orig1 = db.query(Location).filter(Location.district == "Pune").first()
        orig2 = db.query(Location).filter(Location.district == "Nashik").first() or orig1

        plan = ShipmentPlan(
            plan_code=f"PLAN-NOTIF-E2E-{uuid.uuid4().hex[:6].upper()}",
            commodity_id=commodity.id,
            destination_location_id=dest.id,
            planning_status=ShipmentPlanningStatus.PLANNED,
            earliest_pickup_date=date.today(),
            delivery_deadline=date.today() + timedelta(days=2),
            total_planned_quantity_quintals=Decimal("35.00"),
            estimated_gross_merchandise_value=Decimal("87500.00"),
        )
        db.add(plan)
        db.flush()

        db.add(ShipmentPlanPickupStop(
            shipment_plan_id=plan.id,
            stop_sequence=1,
            seller_user_id=user.id,
            seller_name="Khed Potato Farm",
            pickup_location_id=orig1.id,
            allocated_quantity_quintals=Decimal("20.00"),
            earliest_pickup_date=date.today(),
        ))
        db.add(ShipmentPlanPickupStop(
            shipment_plan_id=plan.id,
            stop_sequence=2,
            seller_user_id=user.id,
            seller_name="Manchar Farmers Collective",
            pickup_location_id=orig2.id,
            allocated_quantity_quintals=Decimal("15.00"),
            earliest_pickup_date=date.today(),
        ))
        db.commit()

        # Broadcast TWICE to prove idempotency
        bcast1 = generate_opportunities_for_plan(db, plan.id, force_rebroadcast=True)
        bcast2 = generate_opportunities_for_plan(db, plan.id, force_rebroadcast=True)
        print(f"PLAN_ID={plan.id}|OPP_COUNT={len(bcast1.opportunities)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
