from __future__ import annotations

from typing import Any
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator
from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement


class GeoPoint(TypeDecorator[Any]):
    """PostGIS geography in production, portable text only for SQLite test databases."""

    impl = Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Geography(geometry_type="POINT", srid=4326, spatial_index=False))
        return dialect.type_descriptor(String(64))

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            if isinstance(value, str):
                return WKTElement(value, srid=4326)
            return value
        if isinstance(value, WKTElement):
            return str(value)
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return str(value)
