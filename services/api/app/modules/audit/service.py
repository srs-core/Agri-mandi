from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit_event(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Append an operational audit event; the caller owns the transaction."""

    db.add(
        AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )
