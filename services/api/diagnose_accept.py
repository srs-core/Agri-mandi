from app.db.session import SessionLocal
from sqlalchemy import text
from app.models.entities import User, ProduceLot, Offer, Order, OfferStatus, ProduceLotStatus, Commodity, Location
from app.modules.marketplace.service import accept_offer, create_offer
from app.schemas.marketplace import OfferCreate
from decimal import Decimal
from datetime import date

db = SessionLocal()

print("--- Constraints on produce_lots ---")
constraints = db.execute(text("SELECT conname, pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid WHERE t.relname = 'produce_lots'")).fetchall()
for c in constraints:
    print(c)

print("\n--- Testing offer accept flow ---")
# Find or create a seller
seller = db.query(User).filter(User.email.like("%farmer%")).first()
buyer = db.query(User).filter(User.email.like("%buyer%")).first()
commodity = db.query(Commodity).first()
location = db.query(Location).first()

print(f"Seller: {seller.email if seller else None}, Buyer: {buyer.email if buyer else None}")

# Create a test lot
lot = ProduceLot(
    seller_user_id=seller.id,
    commodity_id=commodity.id,
    pickup_location_id=location.id,
    title="Test Negotiable Lot",
    available_quantity=Decimal("30.00"),
    unit="QTL",
    asking_price_per_unit=None, # Negotiable
    available_from=date.today(),
    status=ProduceLotStatus.PUBLISHED,
)
db.add(lot)
db.commit()
print(f"Created lot {lot.id}, available_qty={lot.available_quantity}, asking_price={lot.asking_price_per_unit}")

# Create offer for full lot quantity
offer_res = create_offer(
    db,
    buyer,
    OfferCreate(
        produce_lot_id=lot.id,
        offered_quantity=Decimal("30.00"),
        offered_price_per_unit=Decimal("1600.00"),
    )
)
print(f"Created offer {offer_res.id}, quantity={offer_res.offered_quantity}, price={offer_res.offered_price_per_unit}")

try:
    order_res = accept_offer(db, seller, offer_res.id)
    print(f"Accept succeeded: Order {order_res.id}")
except Exception as e:
    import traceback
    print("ACCEPT FAILED WITH EXCEPTION:")
    traceback.print_exc()

db.close()
