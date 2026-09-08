from sqlalchemy import text
from app.db.session import SessionLocal

def update_constraint():
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE shipments ALTER COLUMN status TYPE VARCHAR(32);"))
        db.execute(text("ALTER TABLE shipments DROP CONSTRAINT IF EXISTS ck_shipments_shipment_status;"))
        db.execute(text("ALTER TABLE shipments ADD CONSTRAINT ck_shipments_shipment_status CHECK (status IN ('draft', 'scheduled', 'assigned', 'in_pickup', 'dispatched', 'in_transit', 'at_destination', 'delivered', 'cancelled', 'delayed'));"))
        db.commit()
        print("UPDATED_CONSTRAINT_SUCCESS")
    finally:
        db.close()

if __name__ == "__main__":
    update_constraint()
