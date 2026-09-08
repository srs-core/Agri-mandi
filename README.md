# AgriMandi

Pune-first, India-scalable agricultural marketplace and supply-chain orchestration platform for crops and farm produce.

## Architecture & Technology Stack

- **Backend**: FastAPI with PostgreSQL/PostGIS database management and Alembic migrations.
- **Frontend**: React 19 / Vite client with TypeScript.
- **AI / ML Intelligence**: XGBoost price forecasting, market intelligence, and decision support engines.
- **Logistics**: Google OR-Tools multi-stop pickup and route optimization.

## Local Development

1. Copy `.env.example` to `.env` and choose unique development-only database/JWT secrets.
2. Copy `apps/web/.env.example` to `apps/web/.env` if the default API URL is not suitable.
3. Start the stack with `docker compose up --build`.
4. Open `http://localhost:5173`; it displays the application and verified services.

To run the API without Docker, install `services/api/requirements.txt`, set `DATABASE_URL`, apply migrations with `alembic upgrade head`, and start `uvicorn app.main:app --reload` from `services/api`.

## Data Integrity

No buyer, logistics, price, route, availability, or market data is seeded blindly. Development and benchmark data is explicitly sourced with verification metadata.
