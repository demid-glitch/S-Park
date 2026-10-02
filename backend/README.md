# S-Park backend

FastAPI + PostgreSQL + Redis. Step 1 of the build order: core, DB schema, RBAC.

## Run locally

```bash
docker compose up -d            # from repo root: postgres + redis
cd backend
python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # then set JWT_SECRET
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli create-admin 99112233 "Your Name"
.venv/bin/uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs. In development the OTP code is printed to the server log
(no SMS provider yet).

## Tests

```bash
.venv/bin/pytest                                   # SQLite in memory
TEST_DATABASE_URL=postgresql+asyncpg://spark:spark@localhost:5432/spark_test .venv/bin/pytest
```

## Roles and access

| Role | Can do |
|---|---|
| `platform_admin` | Everything: create lots, set commission, manage all users |
| `owner` | Own lots only: edit lot, zones/spots, tariffs, attendants for own lots |
| `attendant` | Assigned lot only: read spots and occupancy, read tariffs |
| `customer` | Own profile and vehicles, browse active lots and tariffs |

Permissions live in `app/core/rbac.py`. Lots outside a user's scope return 404, not 403.
