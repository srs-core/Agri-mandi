from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.models import (
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
    VerificationStatus,
)
from app.modules.marketplace.service import ensure_system_commodities


def _auth_headers(client, email: str, role: str = "farmer") -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "display_name": f"Test {role.capitalize()}",
            "role": role,
        },
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_commodities_listing_and_filtering(client, db) -> None:
    ensure_system_commodities(db)
    resp = client.get("/api/v1/commodities")
    assert resp.status_code == 200
    commodities = resp.json()
    assert len(commodities) >= 20

    veg_resp = client.get("/api/v1/commodities?category=vegetables")
    assert veg_resp.status_code == 200
    veg_list = veg_resp.json()
    assert all(c["category"] == "vegetables" for c in veg_list)
    assert any("Onion" in c["name"] for c in veg_list)


def test_profile_retrieval_and_update(client, db) -> None:
    headers = _auth_headers(client, "profile_farmer@example.com", role="farmer")
    get_resp = client.get("/api/v1/profiles/me", headers=headers)
    assert get_resp.status_code == 200
    profile = get_resp.json()
    assert profile["email"] == "profile_farmer@example.com"
    assert profile["verification_status"] == "pending"

    update_resp = client.put(
        "/api/v1/profiles/me",
        headers=headers,
        json={
            "farm_name": "Green Acres",
            "land_area_hectares": 12.5,
            "primary_location": {
                "name": "Green Acres Farm",
                "village": "Pimpalgaon",
                "taluka": "Niphad",
                "district": "Nashik",
                "state": "Maharashtra",
                "postal_code": "422209",
            },
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["farm_name"] == "Green Acres"
    assert updated["primary_location"]["district"] == "Nashik"


def test_produce_lot_creation_and_marketplace_search(client, db) -> None:
    ensure_system_commodities(db)
    farmer_headers = _auth_headers(client, "seller_farmer@example.com", role="farmer")
    onion = db.scalar(select(Commodity).where(Commodity.name.like("%Onion%")))
    assert onion is not None

    lot_resp = client.post(
        "/api/v1/produce-lots",
        headers=farmer_headers,
        json={
            "commodity_id": str(onion.id),
            "title": "Fresh Nashik Red Onions (Grade A)",
            "available_quantity": 500,
            "unit": "quintal",
            "quality_grade": "Grade A",
            "quality_notes": "Sun-dried, medium size 55mm+",
            "asking_price_per_unit": 2200,
            "available_from": str(date.today()),
            "available_until": str(date.today() + timedelta(days=30)),
            "pickup_location": {
                "name": "Pimpalgaon Mandi Yard",
                "village": "Pimpalgaon",
                "taluka": "Niphad",
                "district": "Nashik",
                "state": "Maharashtra",
                "postal_code": "422209",
            },
        },
    )
    assert lot_resp.status_code == 201
    lot = lot_resp.json()
    assert lot["title"] == "Fresh Nashik Red Onions (Grade A)"
    assert float(lot["available_quantity"]) == 500.0

    # Browse marketplace
    market_resp = client.get("/api/v1/marketplace/produce-lots?category=vegetables")
    assert market_resp.status_code == 200
    market_data = market_resp.json()
    assert "items" in market_data
    assert "total" in market_data
    assert market_data["total"] >= 1
    assert any(l["id"] == lot["id"] for l in market_data["items"])

    # Search query
    search_resp = client.get("/api/v1/marketplace/produce-lots?search=Nashik")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert any(l["id"] == lot["id"] for l in search_data["items"])


def test_commercial_offer_acceptance_and_order_lifecycle(client, db) -> None:
    ensure_system_commodities(db)
    farmer_headers = _auth_headers(client, "deal_farmer@example.com", role="farmer")
    buyer_headers = _auth_headers(client, "deal_buyer@example.com", role="buyer")

    wheat = db.scalar(select(Commodity).where(Commodity.name.like("%Wheat%")))
    assert wheat is not None

    # Farmer creates listing
    lot_resp = client.post(
        "/api/v1/produce-lots",
        headers=farmer_headers,
        json={
            "commodity_id": str(wheat.id),
            "title": "Premium Sharbati Wheat",
            "available_quantity": 1000,
            "unit": "quintal",
            "quality_grade": "Grade A",
            "asking_price_per_unit": 2800,
            "available_from": str(date.today()),
            "pickup_location": {
                "name": "Sehore Mandi",
                "district": "Sehore",
                "state": "Madhya Pradesh",
                "postal_code": "466001",
            },
        },
    )
    assert lot_resp.status_code == 201
    lot_id = lot_resp.json()["id"]

    # Buyer makes an offer for 400 quintals at 2700/quintal
    offer_resp = client.post(
        "/api/v1/offers",
        headers=buyer_headers,
        json={
            "produce_lot_id": lot_id,
            "offered_quantity": 400,
            "offered_price_per_unit": 2700,
        },
    )
    assert offer_resp.status_code == 201
    offer = offer_resp.json()
    assert offer["status"] == "pending"
    assert float(offer["total_amount"]) == 1080000.0
    offer_id = offer["id"]

    # Farmer checks received offers
    received_resp = client.get("/api/v1/offers?role_perspective=received", headers=farmer_headers)
    assert received_resp.status_code == 200
    assert any(o["id"] == offer_id for o in received_resp.json())

    # Farmer accepts the offer
    accept_resp = client.post(f"/api/v1/offers/{offer_id}/accept", headers=farmer_headers)
    assert accept_resp.status_code == 200
    order = accept_resp.json()
    assert order["status"] == "confirmed"
    assert float(order["total_amount"]) == 1080000.0
    order_id = order["id"]

    # Check updated lot available quantity (1000 - 400 = 600)
    updated_lot = client.get(f"/api/v1/produce-lots/{lot_id}").json()
    assert float(updated_lot["available_quantity"]) == 600.0

    # Advance order status: confirmed -> fulfilment -> delivered
    fulfilment_resp = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=farmer_headers,
        json={"status": "fulfilment"},
    )
    assert fulfilment_resp.status_code == 200
    assert fulfilment_resp.json()["status"] == "fulfilment"

    delivered_resp = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=farmer_headers,
        json={"status": "delivered"},
    )
    assert delivered_resp.status_code == 200
    assert delivered_resp.json()["status"] == "delivered"


def test_buyer_requirement_creation_and_listing(client, db) -> None:
    ensure_system_commodities(db)
    buyer_headers = _auth_headers(client, "req_buyer@example.com", role="buyer")
    chana = db.scalar(select(Commodity).where(Commodity.name.like("%Chana%")))
    assert chana is not None

    req_resp = client.post(
        "/api/v1/buyer-requirements",
        headers=buyer_headers,
        json={
            "commodity_id": str(chana.id),
            "required_quantity": 250,
            "unit": "quintal",
            "minimum_quality_grade": "Grade A",
            "target_price_per_unit": 5400,
            "delivery_by": str(date.today() + timedelta(days=15)),
            "delivery_location": {
                "name": "Bhopal Processing Mill",
                "district": "Bhopal",
                "state": "Madhya Pradesh",
            },
        },
    )
    assert req_resp.status_code == 201
    req = req_resp.json()
    assert float(req["required_quantity"]) == 250.0

    # Check buyer's my requirements
    my_reqs = client.get("/api/v1/buyer-requirements/my", headers=buyer_headers).json()
    assert any(r["id"] == req["id"] for r in my_reqs)


def test_admin_verification_and_metrics(client, db) -> None:
    admin_role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN))
    assert admin_role is not None

    admin_user = User(
        email="superadmin@example.com",
        display_name="Super Admin",
        password_hash=hash_password("correct-horse-battery-staple"),
        status=UserStatus.ACTIVE,
    )
    db.add(admin_user)
    db.flush()
    db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
    db.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@example.com", "password": "correct-horse-battery-staple"},
    )
    admin_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Farmer submits verification request
    farmer_headers = _auth_headers(client, "verify_farmer@example.com", role="farmer")
    ver_resp = client.post(
        "/api/v1/profiles/verification-request",
        headers=farmer_headers,
        json={"document_reference": "7/12 land extract #12345"},
    )
    assert ver_resp.status_code == 200
    request_id = ver_resp.json()["id"]

    # Admin lists pending verifications
    ver_get = client.get("/api/v1/admin/verifications?status=pending", headers=admin_headers)
    assert ver_get.status_code == 200
    ver_list = ver_get.json()
    assert any(v["id"] == request_id for v in ver_list)

    # Admin approves verification
    review_resp = client.post(
        f"/api/v1/admin/verifications/{request_id}/review",
        headers=admin_headers,
        json={"status": "verified", "reviewer_notes": "Land records verified against state registry."},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "verified"

    # Farmer profile now reflects verified status
    farmer_profile = client.get("/api/v1/profiles/me", headers=farmer_headers).json()
    assert farmer_profile["verification_status"] == "verified"

    # Admin checks platform metrics
    metrics_get = client.get("/api/v1/admin/metrics", headers=admin_headers)
    assert metrics_get.status_code == 200
    metrics = metrics_get.json()
    assert metrics["total_users"] >= 2
    assert metrics["total_commodities"] >= 1


def test_marketplace_pagination_and_sorting(client, db) -> None:
    ensure_system_commodities(db)
    farmer_headers = _auth_headers(client, "page_farmer@example.com", role="farmer")

    onion = db.scalar(select(Commodity).where(Commodity.name.like("%Onion%")))
    assert onion is not None

    # Create multiple lots with distinct prices and quantities
    lots_data = [
        {"title": "Pagination Lot 1", "available_quantity": 100, "asking_price_per_unit": 1000},
        {"title": "Pagination Lot 2", "available_quantity": 200, "asking_price_per_unit": 2000},
        {"title": "Pagination Lot 3", "available_quantity": 300, "asking_price_per_unit": 3000},
        {"title": "Pagination Lot 4", "available_quantity": 400, "asking_price_per_unit": None},  # Negotiable
    ]

    for data in lots_data:
        resp = client.post(
            "/api/v1/produce-lots",
            headers=farmer_headers,
            json={
                "commodity_id": str(onion.id),
                "title": data["title"],
                "available_quantity": data["available_quantity"],
                "unit": "quintal",
                "quality_grade": "Grade A",
                "asking_price_per_unit": data["asking_price_per_unit"],
                "available_from": str(date.today()),
                "pickup_location": {
                    "name": "Lasalgaon Mandi",
                    "district": "Nashik",
                    "state": "Maharashtra",
                },
            },
        )
        assert resp.status_code == 201

    # 1. Test pagination page_size=2, page=1
    page1_resp = client.get("/api/v1/marketplace/produce-lots?search=Pagination&page=1&page_size=2")
    assert page1_resp.status_code == 200
    page1_data = page1_resp.json()
    assert page1_data["total"] == 4
    assert page1_data["page"] == 1
    assert page1_data["page_size"] == 2
    assert page1_data["total_pages"] == 2
    assert len(page1_data["items"]) == 2

    # 2. Test pagination page=2
    page2_resp = client.get("/api/v1/marketplace/produce-lots?search=Pagination&page=2&page_size=2")
    assert page2_resp.status_code == 200
    page2_data = page2_resp.json()
    assert page2_data["page"] == 2
    assert len(page2_data["items"]) == 2
    # Ensure page 1 and page 2 items are disjoint
    page1_ids = {item["id"] for item in page1_data["items"]}
    page2_ids = {item["id"] for item in page2_data["items"]}
    assert page1_ids.isdisjoint(page2_ids)

    # 3. Test out-of-bounds page
    oob_resp = client.get("/api/v1/marketplace/produce-lots?search=Pagination&page=99&page_size=2")
    assert oob_resp.status_code == 200
    oob_data = oob_resp.json()
    assert oob_data["total"] == 4
    assert oob_data["page"] == 99
    assert len(oob_data["items"]) == 0

    # 4. Test price_asc sort with pagination (fixed prices sort asc, negotiable at end)
    sort_resp = client.get("/api/v1/marketplace/produce-lots?search=Pagination&sort_by=price_asc&page=1&page_size=4")
    assert sort_resp.status_code == 200
    sort_items = sort_resp.json()["items"]
    assert len(sort_items) == 4
    assert sort_items[0]["title"] == "Pagination Lot 1"  # 1000
    assert sort_items[1]["title"] == "Pagination Lot 2"  # 2000
    assert sort_items[2]["title"] == "Pagination Lot 3"  # 3000
    assert sort_items[3]["title"] == "Pagination Lot 4"  # Negotiable

    # 5. Test qty_desc sort with pagination
    qty_resp = client.get("/api/v1/marketplace/produce-lots?search=Pagination&sort_by=qty_desc&page=1&page_size=2")
    assert qty_resp.status_code == 200
    qty_items = qty_resp.json()["items"]
    assert float(qty_items[0]["available_quantity"]) == 400.0
    assert float(qty_items[1]["available_quantity"]) == 300.0

