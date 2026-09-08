# Phase 1 architecture

AgriMandi begins as a modular monolith: the React web client calls a versioned FastAPI service, which owns the transactional PostgreSQL/PostGIS database. Each domain is separated into a module so that future intelligence and logistics capabilities can evolve without turning the Phase 1 system into premature microservices.

## Boundaries reserved for later phases

- `modules/intelligence/contracts.py`: buyer recommendation, price forecasting, demand forecasting, and net-realization interfaces. Implementations intentionally raise `NotImplementedError`.
- `modules/logistics/contracts.py`: logistics planning/assignment interface. It is intentionally unimplemented; no routes, vehicle selections, ETAs, or costs are inferred in Phase 1.
- `data_sources` and `source_attributions`: provenance and verification metadata for future buyer and logistics research imports. Reference data is never assumed current merely because it was imported.

## Geospatial design

`locations.geo_point` compiles to PostGIS `geography(Point, 4326)` in PostgreSQL and has a GIST index. A portable fallback is used in SQLite only for fast unit tests; application development and deployment use PostGIS.

## Produce ownership and aggregation

Every lot has a selling owner (`seller_user_id`). FPO-owned lots may set `owner_fpo_profile_id` and `is_aggregated = true`; `produce_lot_contributions` can record multiple farmer/FPO sources later without changing lot ownership. Aggregation optimization itself remains Phase 2.
