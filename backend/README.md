# S-Park backend

FastAPI + PostgreSQL + Redis. Step 1 of the build order: core, DB schema, RBAC.

## Run locally

```bash
docker compose up -d            # from repo root: postgres + redis
cd backend
python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # then set JWT_SECRET
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli create-admin --username admin_1   # prompts for password
.venv/bin/uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs.

Login:
- Staff with a username: `POST /api/v1/auth/login` with `{"username", "password"}`.
  Locks for 15 min after 10 failed attempts. Change password: `POST /api/v1/auth/password`.
- Phone OTP: `POST /api/v1/auth/otp/request`, then `/otp/verify`. Until an SMS provider is set up,
  the code is printed to the server log (not when `ENVIRONMENT=production`).

## Deploy to Render

`render.yaml` at the repo root creates the API, Postgres and Redis. In the Render dashboard:
New → Blueprint → choose this repo, then enter `INITIAL_ADMIN_USERNAME` and
`INITIAL_ADMIN_PASSWORD` when asked. Each deploy runs migrations, then creates that admin if it
doesn't exist yet (an existing admin's password is never overwritten).

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
