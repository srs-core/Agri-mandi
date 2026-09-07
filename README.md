# AgriMandi

Pune-first, India-scalable agricultural marketplace and supply-chain orchestration platform for crops and farm produce.

The repository currently contains the **Phase 1 foundation checkpoint**: a React/Vite health-check client, FastAPI service, PostgreSQL/PostGIS local development configuration, database migration, and authentication/RBAC foundation. Marketplace workflows and intelligence are deliberately not included yet.

## Local development

1. Copy `.env.example` to `.env` and choose unique development-only database/JWT secrets.
2. Copy `apps/web/.env.example` to `apps/web/.env` if the default API URL is not suitable.
3. Start the stack with `docker compose up --build`.
4. Open `http://localhost:5173`; it displays the result of the API health check.

To run the API without Docker, install `services/api/requirements.txt`, set `DATABASE_URL`, apply migrations with `alembic upgrade head`, and start `uvicorn app.main:app --reload` from `services/api`.

## Data integrity

No buyer, logistics, price, route, availability, or market data is seeded. Any future development data must be explicitly marked mock and carry source/verification metadata.
