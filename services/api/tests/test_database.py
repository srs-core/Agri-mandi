import uuid
from sqlalchemy import inspect, select, text

from app.core.security import hash_password
from app.models import Role, RoleName, User, UserStatus
from app.modules.auth.service import ensure_system_roles


def test_initial_schema_contains_phase_one_tables(db) -> None:
    expected_tables = {
        "users", "roles", "user_roles", "locations", "farmer_profiles", "fpo_profiles",
        "buyer_profiles", "transporter_profiles", "commodities", "produce_lots",
        "buyer_requirements", "offers", "orders", "order_items", "verification_requests",
        "audit_events", "notifications", "data_sources", "source_attributions", "refresh_tokens",
    }
    assert expected_tables.issubset(set(inspect(db.bind).get_table_names()))


def test_system_roles_are_initialized(client, db) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    roles = set(db.scalars(select(Role.name)).all())
    assert roles == set(RoleName)


def test_ensure_system_roles_reconciles_prepopulated_lowercase_roles(db) -> None:
    # Clear existing roles to simulate a fresh migration state seeded with raw lowercase strings
    db.execute(text("DELETE FROM user_roles"))
    db.execute(text("DELETE FROM roles"))
    db.commit()

    # Seed raw lowercase role values matching Alembic 20260828_0001 seed data
    db.add_all(
        [
            Role(id=uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e01"), name=RoleName.FARMER, description="System role: farmer"),
            Role(id=uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e02"), name=RoleName.FPO, description="System role: fpo"),
            Role(id=uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e03"), name=RoleName.BUYER, description="System role: buyer"),
            Role(id=uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e04"), name=RoleName.TRANSPORTER, description="System role: transporter"),
            Role(id=uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e05"), name=RoleName.ADMIN, description="System role: admin"),
            Role(id=uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e06"), name=RoleName.GOVERNMENT, description="System role: government"),
        ]
    )
    db.commit()

    # ensure_system_roles should load existing lowercase values without LookupError
    ensure_system_roles(db)

    # Verify all 6 roles are present and correctly mapped to RoleName enum
    loaded_roles = set(db.scalars(select(Role.name)).all())
    assert loaded_roles == set(RoleName)

    # Verify raw database representation remains lowercase strings
    raw_names = set(db.execute(text("SELECT name FROM roles")).scalars().all())
    assert raw_names == {"farmer", "fpo", "buyer", "transporter", "admin", "government"}


def test_enum_column_persists_canonical_lowercase_values(db) -> None:
    # Test User model with UserStatus enum
    test_user = User(
        email="enum_test@example.com",
        display_name="Enum Tester",
        password_hash=hash_password("correct-horse-battery-staple"),
        status=UserStatus.ACTIVE,
    )
    db.add(test_user)
    db.commit()

    # Verify raw SQL query returns lowercase "active"
    raw_status = db.execute(
        text("SELECT status FROM users WHERE email = :email"),
        {"email": "enum_test@example.com"},
    ).scalar_one()
    assert raw_status == "active"

    # Verify ORM query deserializes to UserStatus.ACTIVE enum member
    loaded_user = db.scalar(select(User).where(User.email == "enum_test@example.com"))
    assert loaded_user is not None
    assert loaded_user.status == UserStatus.ACTIVE
