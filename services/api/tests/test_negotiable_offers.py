from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.entities import (
    Commodity,
    CommodityCategory,
    Location,
    Offer,
    OfferStatus,
    Order,
    OrderStatus,
    ProduceLot,
    ProduceLotStatus,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
)
from app.modules.marketplace.service import (
    accept_offer,
    counter_offer,
    create_offer,
    ensure_system_commodities,
    get_produce_lot_detail,
    list_offers,
    reject_offer,
    withdraw_offer,
)
from app.schemas.marketplace import CounterOfferCreate, OfferCreate


def _get_or_create_roles(db: Session) -> dict[str, Role]:
    roles = {}
    for role_name in [RoleName.FARMER, RoleName.BUYER, RoleName.FPO, RoleName.ADMIN]:
        role = db.scalar(select(Role).where(Role.name == role_name))
        if not role:
            role = Role(name=role_name, description=f"{role_name.value} role")
            db.add(role)
            db.flush()
        roles[role_name.value] = role
    db.commit()
    return roles


def _create_user(db: Session, email: str, role_name: str = "farmer") -> User:
    roles_map = _get_or_create_roles(db)
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(
            email=email,
            password_hash="test-hash",
            display_name=f"User {email.split('@')[0]}",
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.flush()
        ur = UserRole(user_id=user.id, role_id=roles_map[role_name].id)
        db.add(ur)
        db.commit()
        db.refresh(user)
    return user


def _get_commodity_and_location(db: Session) -> tuple[Commodity, Location]:
    ensure_system_commodities(db)
    commodity = db.scalar(select(Commodity))
    if not commodity:
        commodity = Commodity(name="Potato Jyoti", category=CommodityCategory.VEGETABLES, variety="Jyoti")
        db.add(commodity)
        db.flush()

    location = db.scalar(select(Location))
    if not location:
        location = Location(
            name="Agra Mandi Hub",
            state="Uttar Pradesh",
            district="Agra",
            taluka="Agra",
            village="Agra Rural",
            postal_code="282001",
            latitude=Decimal("27.1767"),
            longitude=Decimal("78.0081"),
        )
        db.add(location)
        db.flush()
    db.commit()
    return commodity, location


def test_negotiable_produce_lot_price_mode(db: Session) -> None:
    """Verify price_mode is NEGOTIABLE when asking price is omitted, and FIXED_PRICE when provided."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    commodity, location = _get_commodity_and_location(db)

    lot_neg = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="Negotiable Potato Lot",
        available_quantity=Decimal("50.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot_neg)

    lot_fix = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="Fixed Price Potato Lot",
        available_quantity=Decimal("50.000"),
        unit="QTL",
        asking_price_per_unit=Decimal("1800.00"),
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot_fix)
    db.commit()

    detail_neg = get_produce_lot_detail(db, lot_neg.id)
    detail_fix = get_produce_lot_detail(db, lot_fix.id)

    assert detail_neg.price_mode == "NEGOTIABLE"
    assert detail_neg.asking_price_per_unit is None

    assert detail_fix.price_mode == "FIXED_PRICE"
    assert detail_fix.asking_price_per_unit == Decimal("1800.00")


def test_buyer_creates_offer_on_negotiable_lot(db: Session) -> None:
    """Initial buyer offer creates the first proposal in history and sets required responder to seller."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer_res = create_offer(
        db,
        buyer,
        OfferCreate(
            produce_lot_id=lot.id,
            offered_quantity=Decimal("30.000"),
            offered_price_per_unit=Decimal("1600.00"),
            notes="Initial offer for bulk purchase",
        ),
    )

    assert offer_res.status == OfferStatus.PENDING
    assert offer_res.price_mode == "NEGOTIABLE"
    assert offer_res.current_price_per_unit == Decimal("1600.00")
    assert offer_res.current_quantity == Decimal("30.000")
    assert offer_res.current_proposer_user_id == buyer.id
    assert offer_res.current_proposer_role == "buyer"
    assert offer_res.response_required_from_user_id == farmer.id
    assert len(offer_res.history) == 1
    assert offer_res.history[0].proposer_role == "buyer"
    assert offer_res.history[0].price_per_unit == Decimal("1600.00")
    assert offer_res.history[0].status_at_step == "proposed"
    assert offer_res.history[0].notes == "Initial offer for bulk purchase"


def test_farmer_submits_counter_offer(db: Session) -> None:
    """Farmer can submit counter-offer; status becomes COUNTERED and response required flips to buyer."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer_res = create_offer(
        db,
        buyer,
        OfferCreate(
            produce_lot_id=lot.id,
            offered_quantity=Decimal("30.000"),
            offered_price_per_unit=Decimal("1600.00"),
        ),
    )

    counter_res = counter_offer(
        db,
        farmer,
        offer_res.id,
        CounterOfferCreate(
            price_per_unit=Decimal("1750.00"),
            quantity=Decimal("30.000"),
            notes="Quality is Grade A Jyoti, ₹1750 is fair rate.",
        ),
    )

    assert counter_res.status == OfferStatus.COUNTERED
    assert counter_res.current_price_per_unit == Decimal("1750.00")
    assert counter_res.current_proposer_user_id == farmer.id
    assert counter_res.current_proposer_role == "seller"
    assert counter_res.response_required_from_user_id == buyer.id
    assert len(counter_res.history) == 2
    assert counter_res.history[0].status_at_step == "countered"
    assert counter_res.history[1].status_at_step == "proposed"
    assert counter_res.history[1].price_per_unit == Decimal("1750.00")
    assert counter_res.history[1].notes == "Quality is Grade A Jyoti, ₹1750 is fair rate."


def test_multi_round_negotiation_and_acceptance(db: Session) -> None:
    """Complete round-trip: Buyer offers ₹1600 -> Farmer counters ₹1750 -> Buyer counters ₹1700 -> Farmer accepts ₹1700 -> Order confirmed at ₹1700."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    # Step 1: Buyer offers 1600
    offer1 = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    # Step 2: Farmer counters 1750
    offer2 = counter_offer(
        db,
        farmer,
        offer1.id,
        CounterOfferCreate(price_per_unit=Decimal("1750.00")),
    )

    # Step 3: Buyer counters 1700
    offer3 = counter_offer(
        db,
        buyer,
        offer2.id,
        CounterOfferCreate(price_per_unit=Decimal("1700.00"), notes="Meet in middle at ₹1700/QTL"),
    )

    assert offer3.status == OfferStatus.COUNTERED
    assert offer3.current_price_per_unit == Decimal("1700.00")
    assert offer3.response_required_from_user_id == farmer.id
    assert len(offer3.history) == 3

    # Step 4: Farmer accepts ₹1700
    order_res = accept_offer(db, farmer, offer3.id)

    assert order_res.status.value == "confirmed"
    assert order_res.total_amount == Decimal("30.000") * Decimal("1700.00")
    assert len(order_res.items) == 1
    assert order_res.items[0].agreed_price_per_unit == Decimal("1700.00")
    assert order_res.items[0].quantity == Decimal("30.000")

    # Verify lot is marked SOLD and available quantity is 0
    db.refresh(lot)
    assert lot.available_quantity == Decimal("0.000")
    assert lot.status == ProduceLotStatus.SOLD

    # Verify offer is ACCEPTED and history shows final accepted proposal
    offer_final = list_offers(db, farmer, lot_id=lot.id)[0]
    assert offer_final.status == OfferStatus.ACCEPTED
    assert offer_final.history[-1].status_at_step == "accepted"
    assert offer_final.history[-1].price_per_unit == Decimal("1700.00")


def test_buyer_accepts_farmer_counter_offer(db: Session) -> None:
    """Bilateral acceptance: Buyer can accept Farmer's counter-offer."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer1 = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    offer2 = counter_offer(
        db,
        farmer,
        offer1.id,
        CounterOfferCreate(price_per_unit=Decimal("1750.00")),
    )

    # Buyer accepts farmer's ₹1750 counter-offer
    order_res = accept_offer(db, buyer, offer2.id)

    assert order_res.status.value == "confirmed"
    assert order_res.total_amount == Decimal("30.000") * Decimal("1750.00")
    assert order_res.items[0].agreed_price_per_unit == Decimal("1750.00")


def test_cannot_counter_own_proposal(db: Session) -> None:
    """User cannot counter their own proposal before counterparty responds."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer1 = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    with pytest.raises(ApiError) as exc_info:
        counter_offer(
            db,
            buyer,
            offer1.id,
            CounterOfferCreate(price_per_unit=Decimal("1650.00")),
        )
    assert exc_info.value.code in ("not_your_turn", "self_counter_forbidden")


def test_cannot_accept_own_proposal(db: Session) -> None:
    """Proposer cannot accept their own proposal."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer1 = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    with pytest.raises(ApiError) as exc_info:
        accept_offer(db, buyer, offer1.id)
    assert exc_info.value.code in ("not_your_turn", "not_authorized")


def test_unauthorized_user_cannot_counter_or_accept(db: Session) -> None:
    """Third-party user cannot interact with another parties' offer."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)

    other_user = User(
        email=f"intruder_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
        display_name="Intruder",
        status=UserStatus.ACTIVE,
    )
    db.add(other_user)
    db.commit()

    offer1 = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    with pytest.raises(ApiError) as exc_info:
        counter_offer(db, other_user, offer1.id, CounterOfferCreate(price_per_unit=Decimal("1500.00")))
    assert exc_info.value.code == "not_authorized"

    with pytest.raises(ApiError) as exc_info:
        accept_offer(db, other_user, offer1.id)
    assert exc_info.value.code == "not_authorized"


def test_sold_lot_cannot_receive_new_offers(db: Session) -> None:
    """A SOLD produce lot (available_quantity = 0) cannot receive new offers."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="Sold Lot",
        available_quantity=Decimal("0.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.SOLD,
    )
    db.add(lot)
    db.commit()

    with pytest.raises(ApiError) as exc_info:
        create_offer(
            db,
            buyer,
            OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("10.000"), offered_price_per_unit=Decimal("1600.00")),
        )
    assert exc_info.value.code in ("lot_not_available", "lot_sold")


def test_counter_quantity_cannot_exceed_available_quantity(db: Session) -> None:
    """Counter-offer cannot demand more quantity than available on the lot."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer1 = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    with pytest.raises(ApiError) as exc_info:
        counter_offer(
            db,
            farmer,
            offer1.id,
            CounterOfferCreate(price_per_unit=Decimal("1700.00"), quantity=Decimal("50.000")),
        )
    assert exc_info.value.code == "quantity_exceeded"


def test_reject_counter_offer(db: Session) -> None:
    """Responding party can decline counter-offer, marking offer as DECLINED."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer1 = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    offer2 = counter_offer(
        db,
        farmer,
        offer1.id,
        CounterOfferCreate(price_per_unit=Decimal("1750.00")),
    )

    decline_res = reject_offer(db, buyer, offer2.id)

    assert decline_res.status == OfferStatus.DECLINED
    assert decline_res.history[-1].status_at_step == "declined"


def test_withdraw_offer_by_proposer(db: Session) -> None:
    """Proposer can withdraw their proposal before counterparty responds."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer1 = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    withdraw_res = withdraw_offer(db, buyer, offer1.id)

    assert withdraw_res.status == OfferStatus.WITHDRAWN
    assert withdraw_res.history[-1].status_at_step == "withdrawn"


def test_idempotent_accept_offer(db: Session) -> None:
    """Calling accept_offer multiple times returns existing order safely without duplicate rows or constraint violations."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 QTL Jyoti Potato",
        available_quantity=Decimal("30.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1600.00")),
    )

    order1 = accept_offer(db, farmer, offer.id)
    order2 = accept_offer(db, farmer, offer.id)

    assert order1.id == order2.id
    assert order1.total_amount == order2.total_amount


def test_http_endpoints_negotiation_flow(client: TestClient, db: Session) -> None:
    """Test the full HTTP REST API endpoints for offer creation, counter-offer, and acceptance."""
    # Register and login farmer & buyer
    farmer_email = f"farmer_{uuid4().hex[:8]}@example.com"
    buyer_email = f"buyer_{uuid4().hex[:8]}@example.com"
    pwd = "password123!"

    client.post("/api/v1/auth/register", json={"email": farmer_email, "password": pwd, "display_name": "Ramesh Farmer", "role": "farmer"})
    farmer_token = client.post("/api/v1/auth/login", json={"email": farmer_email, "password": pwd}).json()["access_token"]
    farmer_headers = {"Authorization": f"Bearer {farmer_token}"}

    client.post("/api/v1/auth/register", json={"email": buyer_email, "password": pwd, "display_name": "Suresh Buyer", "role": "buyer"})
    buyer_token = client.post("/api/v1/auth/login", json={"email": buyer_email, "password": pwd}).json()["access_token"]
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    commodity, location = _get_commodity_and_location(db)

    # 1. Farmer creates negotiable lot
    create_lot_resp = client.post(
        "/api/v1/produce-lots",
        headers=farmer_headers,
        json={
            "commodity_id": str(commodity.id),
            "title": "30 QTL Negotiable Potato",
            "available_quantity": 30.0,
            "unit": "QTL",
            "pickup_location_id": str(location.id),
        },
    )
    assert create_lot_resp.status_code == 201, create_lot_resp.text
    lot_id = create_lot_resp.json()["id"]

    # 2. Buyer submits initial offer ₹1600
    offer_resp = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 30.0, "offered_price_per_unit": 1600.0, "notes": "Offer ₹1600/QTL"},
    )
    assert offer_resp.status_code == 201, offer_resp.text
    offer_id = offer_resp.json()["id"]
    assert offer_resp.json()["price_mode"] == "NEGOTIABLE"
    assert offer_resp.json()["status"] == "pending"

    # 3. Farmer counters ₹1750
    counter1_resp = client.post(
        f"/api/v1/offers/{offer_id}/counter",
        headers=farmer_headers,
        json={"price_per_unit": 1750.0, "quantity": 30.0, "notes": "Counter ₹1750/QTL"},
    )
    assert counter1_resp.status_code == 200, counter1_resp.text
    assert counter1_resp.json()["status"] == "countered"
    assert float(counter1_resp.json()["current_price_per_unit"]) == 1750.0

    # 4. Buyer counters ₹1700
    counter2_resp = client.post(
        f"/api/v1/offers/{offer_id}/counter",
        headers=buyer_headers,
        json={"price_per_unit": 1700.0, "quantity": 30.0, "notes": "Counter ₹1700/QTL"},
    )
    assert counter2_resp.status_code == 200, counter2_resp.text
    assert float(counter2_resp.json()["current_price_per_unit"]) == 1700.0

    # 5. Farmer accepts ₹1700
    accept_resp = client.post(
        f"/api/v1/offers/{offer_id}/accept",
        headers=farmer_headers,
    )
    assert accept_resp.status_code == 200, accept_resp.text
    order_data = accept_resp.json()
    assert order_data["status"] == "confirmed"
    assert float(order_data["total_amount"]) == 51000.0
    assert float(order_data["items"][0]["agreed_price_per_unit"]) == 1700.0


def test_fixed_price_offer_direct_acceptance(client: TestClient, db: Session) -> None:
    """Fixed price listing can be directly offered and accepted without counter offers."""
    farmer_email = f"farmer_{uuid4().hex[:8]}@example.com"
    buyer_email = f"buyer_{uuid4().hex[:8]}@example.com"
    pwd = "password123!"

    client.post("/api/v1/auth/register", json={"email": farmer_email, "password": pwd, "display_name": "Fixed Farmer", "role": "farmer"})
    farmer_token = client.post("/api/v1/auth/login", json={"email": farmer_email, "password": pwd}).json()["access_token"]
    farmer_headers = {"Authorization": f"Bearer {farmer_token}"}

    client.post("/api/v1/auth/register", json={"email": buyer_email, "password": pwd, "display_name": "Fixed Buyer", "role": "buyer"})
    buyer_token = client.post("/api/v1/auth/login", json={"email": buyer_email, "password": pwd}).json()["access_token"]
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    commodity, location = _get_commodity_and_location(db)

    # 1. Create fixed price lot ₹2000
    create_lot_resp = client.post(
        "/api/v1/produce-lots",
        headers=farmer_headers,
        json={
            "commodity_id": str(commodity.id),
            "title": "20 QTL Fixed Price Onion",
            "available_quantity": 20.0,
            "unit": "QTL",
            "asking_price_per_unit": 2000.0,
            "pickup_location_id": str(location.id),
        },
    )
    lot_id = create_lot_resp.json()["id"]

    # 2. Buyer offers ₹2000
    offer_resp = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 20.0, "offered_price_per_unit": 2000.0},
    )
    offer_id = offer_resp.json()["id"]

    # 3. Farmer accepts
    accept_resp = client.post(f"/api/v1/offers/{offer_id}/accept", headers=farmer_headers)
    assert accept_resp.status_code == 200
    assert float(accept_resp.json()["total_amount"]) == 40000.0


def test_list_offers_filtering_sent_and_received(db: Session) -> None:
    """list_offers correctly segments offers into sent and received perspectives."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="15 QTL Jyoti Potato",
        available_quantity=Decimal("15.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    offer = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("15.000"), offered_price_per_unit=Decimal("1650.00")),
    )

    received_by_farmer = list_offers(db, farmer, role_perspective="received")
    sent_by_farmer = list_offers(db, farmer, role_perspective="sent")
    received_by_buyer = list_offers(db, buyer, role_perspective="received")
    sent_by_buyer = list_offers(db, buyer, role_perspective="sent")

    assert any(o.id == offer.id for o in received_by_farmer)
    assert not any(o.id == offer.id for o in sent_by_farmer)
    assert not any(o.id == offer.id for o in received_by_buyer)
    assert any(o.id == offer.id for o in sent_by_buyer)


def test_notifications_emitted_for_offer_counter_and_accept(db: Session) -> None:
    """Notifications are emitted to the recipient upon offer creation, counter, and acceptance."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="25 QTL Jyoti Potato",
        available_quantity=Decimal("25.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    # 1. Offer creation -> notify seller
    offer = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("25.000"), offered_price_per_unit=Decimal("1600.00")),
    )
    db.commit()

    # 2. Counter offer -> notify buyer
    counter = counter_offer(
        db,
        farmer,
        offer.id,
        CounterOfferCreate(price_per_unit=Decimal("1700.00")),
    )
    db.commit()

    # 3. Accept -> notify seller
    order = accept_offer(db, buyer, counter.id)
    db.commit()

    assert order.status.value == "confirmed"
    assert order.total_amount == Decimal("25.000") * Decimal("1700.00")


def test_stale_proposal_protection(db: Session) -> None:
    """A user cannot accept or revert to a superseded proposal after a counter-offer exists."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="20 QTL Potato",
        available_quantity=Decimal("20.000"),
        unit="QTL",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    # 1. Buyer offers 1500
    offer = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("20.000"), offered_price_per_unit=Decimal("1500.00")),
    )

    # 2. Farmer counters 1800
    counter = counter_offer(
        db,
        farmer,
        offer.id,
        CounterOfferCreate(price_per_unit=Decimal("1800.00")),
    )

    # Farmer cannot accept the offer now because response_required is Buyer and current proposal is 1800
    with pytest.raises(ApiError) as exc_info:
        accept_offer(db, farmer, offer.id)
    assert exc_info.value.code == "not_your_turn"

    # Buyer accepts current proposal (1800) -> order confirmed at 1800, not 1500
    order = accept_offer(db, buyer, offer.id)
    assert order.total_amount == Decimal("20.000") * Decimal("1800.00")
    assert order.items[0].agreed_price_per_unit == Decimal("1800.00")


def test_offer_quantity_boundary_checks(db: Session) -> None:
    """Test quantity boundary conditions: equal, below, slightly above, and massively above available quantity."""
    farmer = _create_user(db, f"farmer_{uuid4().hex[:8]}@example.com", "farmer")
    buyer = _create_user(db, f"buyer_{uuid4().hex[:8]}@example.com", "buyer")
    commodity, location = _get_commodity_and_location(db)

    lot = ProduceLot(
        seller_user_id=farmer.id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title="30 Box Alphonso Mango",
        available_quantity=Decimal("30.000"),
        unit="box (20kg)",
        asking_price_per_unit=None,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    # 1. Exactly equal to availability -> success
    offer_equal = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.000"), offered_price_per_unit=Decimal("1500.00")),
    )
    assert offer_equal.offered_quantity == Decimal("30.000")
    assert offer_equal.total_amount == Decimal("45000.00")

    # 2. Below availability -> success
    offer_below = create_offer(
        db,
        buyer,
        OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("10.000"), offered_price_per_unit=Decimal("1500.00")),
    )
    assert offer_below.offered_quantity == Decimal("10.000")
    assert offer_below.total_amount == Decimal("15000.00")

    # 3. Slightly above availability (30.001 vs 30) -> rejected with 400 quantity_exceeded
    with pytest.raises(ApiError) as exc_info_slight:
        create_offer(
            db,
            buyer,
            OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("30.001"), offered_price_per_unit=Decimal("1500.00")),
        )
    assert exc_info_slight.value.status_code == 400
    assert exc_info_slight.value.code == "quantity_exceeded"
    assert "cannot exceed" in exc_info_slight.value.message.lower() or "exceeds" in exc_info_slight.value.message.lower()

    # 4. Massively above availability (3000 vs 30) -> rejected with 400 quantity_exceeded
    with pytest.raises(ApiError) as exc_info_massive:
        create_offer(
            db,
            buyer,
            OfferCreate(produce_lot_id=lot.id, offered_quantity=Decimal("3000.000"), offered_price_per_unit=Decimal("1500.00")),
        )
    assert exc_info_massive.value.status_code == 400
    assert exc_info_massive.value.code == "quantity_exceeded"
    assert "exceeds available quantity of 30.000 box (20kg)" in exc_info_massive.value.message


def test_offer_http_validation_status_codes(client: TestClient, db: Session) -> None:
    """HTTP API test verifying 400 for business logic (quantity_exceeded) and 422 for schema invalidation."""
    farmer_email = f"farmer_{uuid4().hex[:8]}@example.com"
    buyer_email = f"buyer_{uuid4().hex[:8]}@example.com"
    pwd = "password123!"

    client.post("/api/v1/auth/register", json={"email": farmer_email, "password": pwd, "display_name": "Fruit Farmer", "role": "farmer"})
    farmer_token = client.post("/api/v1/auth/login", json={"email": farmer_email, "password": pwd}).json()["access_token"]
    farmer_headers = {"Authorization": f"Bearer {farmer_token}"}

    client.post("/api/v1/auth/register", json={"email": buyer_email, "password": pwd, "display_name": "Fruit Buyer", "role": "buyer"})
    buyer_token = client.post("/api/v1/auth/login", json={"email": buyer_email, "password": pwd}).json()["access_token"]
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    commodity, location = _get_commodity_and_location(db)

    # Farmer lists 30 box lot
    lot_resp = client.post(
        "/api/v1/produce-lots",
        headers=farmer_headers,
        json={
            "commodity_id": str(commodity.id),
            "title": "Ratnagiri Alphonso Mango 30 Box Lot",
            "available_quantity": 30.0,
            "unit": "box (20kg)",
            "pickup_location_id": str(location.id),
        },
    )
    assert lot_resp.status_code == 201
    lot_id = lot_resp.json()["id"]

    # 1. Massive quantity: 3000 -> 400
    r_massive = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 3000.0, "offered_price_per_unit": 1500.0},
    )
    assert r_massive.status_code == 400
    assert r_massive.json()["error"]["code"] == "quantity_exceeded"
    assert "30.000 box (20kg)" in r_massive.json()["error"]["message"]

    # 2. Slight excess: 30.001 -> 400
    r_slight = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 30.001, "offered_price_per_unit": 1500.0},
    )
    assert r_slight.status_code == 400
    assert r_slight.json()["error"]["code"] == "quantity_exceeded"

    # 3. Zero quantity -> 422
    r_zero_qty = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 0, "offered_price_per_unit": 1500.0},
    )
    assert r_zero_qty.status_code == 422

    # 4. Negative quantity -> 422
    r_neg_qty = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": -5.0, "offered_price_per_unit": 1500.0},
    )
    assert r_neg_qty.status_code == 422

    # 5. Non-numeric quantity -> 422
    r_nan_qty = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": "thirty", "offered_price_per_unit": 1500.0},
    )
    assert r_nan_qty.status_code == 422

    # 6. Missing price -> 422
    r_missing_price = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 10.0},
    )
    assert r_missing_price.status_code == 422

    # 7. Zero price -> 422
    r_zero_price = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 10.0, "offered_price_per_unit": 0},
    )
    assert r_zero_price.status_code == 422

    # 8. Negative price -> 422
    r_neg_price = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 10.0, "offered_price_per_unit": -1500.0},
    )
    assert r_neg_price.status_code == 422

    # 9. Valid 10 box @ 1500 -> 201 with total 15,000
    r_valid = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 10.0, "offered_price_per_unit": 1500.0},
    )
    assert r_valid.status_code == 201
    valid_data = r_valid.json()
    assert float(valid_data["offered_quantity"]) == 10.0
    assert float(valid_data["offered_price_per_unit"]) == 1500.0
    assert float(valid_data["total_amount"]) == 15000.0
    assert valid_data["unit"] == "box (20kg)"


def test_stale_availability_protected_by_current_db_validation(client: TestClient, db: Session) -> None:
    """Verify that a second buyer cannot submit for old available quantity after an order is confirmed."""
    farmer_email = f"farmer_{uuid4().hex[:8]}@example.com"
    buyer1_email = f"buyer1_{uuid4().hex[:8]}@example.com"
    buyer2_email = f"buyer2_{uuid4().hex[:8]}@example.com"
    pwd = "password123!"

    client.post("/api/v1/auth/register", json={"email": farmer_email, "password": pwd, "display_name": "Farmer", "role": "farmer"})
    farmer_token = client.post("/api/v1/auth/login", json={"email": farmer_email, "password": pwd}).json()["access_token"]
    farmer_headers = {"Authorization": f"Bearer {farmer_token}"}

    client.post("/api/v1/auth/register", json={"email": buyer1_email, "password": pwd, "display_name": "Buyer 1", "role": "buyer"})
    buyer1_token = client.post("/api/v1/auth/login", json={"email": buyer1_email, "password": pwd}).json()["access_token"]
    buyer1_headers = {"Authorization": f"Bearer {buyer1_token}"}

    client.post("/api/v1/auth/register", json={"email": buyer2_email, "password": pwd, "display_name": "Buyer 2", "role": "buyer"})
    buyer2_token = client.post("/api/v1/auth/login", json={"email": buyer2_email, "password": pwd}).json()["access_token"]
    buyer2_headers = {"Authorization": f"Bearer {buyer2_token}"}

    commodity, location = _get_commodity_and_location(db)

    # Initial lot: 30 box
    lot_resp = client.post(
        "/api/v1/produce-lots",
        headers=farmer_headers,
        json={
            "commodity_id": str(commodity.id),
            "title": "30 Box Mango Stale Test",
            "available_quantity": 30.0,
            "unit": "box (20kg)",
            "pickup_location_id": str(location.id),
        },
    )
    lot_id = lot_resp.json()["id"]

    # Buyer 1 offers 20 boxes
    offer1_resp = client.post(
        "/api/v1/offers",
        headers=buyer1_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 20.0, "offered_price_per_unit": 1500.0},
    )
    assert offer1_resp.status_code == 201
    offer1_id = offer1_resp.json()["id"]

    # Farmer accepts Buyer 1's offer -> lot available quantity drops to 10 box
    accept_resp = client.post(f"/api/v1/offers/{offer1_id}/accept", headers=farmer_headers)
    assert accept_resp.status_code == 200

    # Verify current DB availability is 10
    lot_detail = client.get(f"/api/v1/produce-lots/{lot_id}").json()
    assert float(lot_detail["available_quantity"]) == 10.0

    # Buyer 2 has stale browser loaded when lot had 30 boxes, now attempts to offer 20 boxes
    # Backend MUST reject with 400 (not 500) based on CURRENT DB quantity (10)
    stale_resp = client.post(
        "/api/v1/offers",
        headers=buyer2_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 20.0, "offered_price_per_unit": 1500.0},
    )
    assert stale_resp.status_code == 400
    assert stale_resp.json()["error"]["code"] == "quantity_exceeded"
    assert "10.000 box (20kg)" in stale_resp.json()["error"]["message"]

    # But Buyer 2 offering 10 boxes (the remaining available) succeeds
    valid_resp = client.post(
        "/api/v1/offers",
        headers=buyer2_headers,
        json={"produce_lot_id": lot_id, "offered_quantity": 10.0, "offered_price_per_unit": 1500.0},
    )
    assert valid_resp.status_code == 201
    assert float(valid_resp.json()["offered_quantity"]) == 10.0



