# EventForge

A backend system that entails selling event seats with time-boxed holds, race-safe confirmation logic, and database-level guarantees. 

## Features
- **Shows & Seats:** Each show manages its own normalized, deduplicated seat labels (`Seat(seat_number, show_id)`).
- **Reservation lifecycle:** Seats progress through `HELD → CONFIRMED → (CANCELLED | EXPIRED)` with automatic expiry at `hold_expiry`.
- **Race-safety:** Partial unique index ensures one active reservation per seat.
- **Idempotent workflows:** Confirming or releasing the same reservation twice returns the current state instead of failing.
- **Availability view:** Per-show availability reports each seat as `AVAILABLE`, `HELD` (with expiry), or `CONFIRMED`.
- **Tests:** Pytest suite covers API flows, DB constraints, and expiry edge cases.

## Stack
- FastAPI with Pydantic validation
- SQLAlchemy ORM
- PostgreSQL
- Alembic migrations
- Pytest 
- Uvicorn

## Data Model (Simplified)
```
User(id, name, phone_number, email, password)
Show(id, title, venue, starts_at)
Seat(id, show_id -> Show.id, seat_number UNIQUE per show)
Reservation(
  id, user_id -> User.id, seat_id -> Seat.id,
  status ∈ {HELD, CONFIRMED, EXPIRED, CANCELLED},
  hold_expiry, created_at, updated_at
)

-- Prevent double booking
CREATE UNIQUE INDEX unique_active_reservation_per_seat
ON reservations(seat_id)
WHERE status IN ('HELD','CONFIRMED');
```

## API
- `POST /users/` → create a user `{ name, phone_number, email, password }`.
- `POST /shows/` → create a show `{ title, venue, starts_at }`.
- `POST /shows/{show_id}/seats` → bulk create seats, normalizing labels (`["A1", "A2", " c5 "] → ["A1","A2","C5"]`).
- `GET /shows/{show_id}/seats` → list seats for a show.
- `GET /shows/{show_id}/availability` → availability snapshot (`{ seat_id, seat_number, status, hold_expiry? }`).
- `POST /reservations/{user_id}/hold` → hold a seat for 1–20 minutes.
- `POST /reservations/{reservation_id}/confirm` → lock & confirm, idempotent; rejects expired holds.
- `POST /reservations/{reservation_id}/release` → cancel a held seat, idempotent.

Interactive docs: http://127.0.0.1:8001/docs

## Getting Started
1. **Python environment**
   ```bash
   python -m venv reserve-env
   source reserve-env/bin/activate
   pip install -r requirements.txt
   ```
2. **PostgreSQL**
   ```bash
   createdb event_ticketing
   export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/event_ticketing"
   ```
3. **Run migrations**
   ```bash
   alembic upgrade head
   ```
4. **Start the API**
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

Coverage highlights:
- Seat label normalization and duplicate protection (409 conflict)
- Successful holds with future `hold_expiry`
- Conflicts when competing users attempt to hold the same seat
- Confirm success path plus forced expiry to `EXPIRED`

## Design Notes
- **Normalization:** Seat labels are trimmed & uppercased before persistence, with request-side duplicate checks plus DB uniqueness.
- **Race safety:** The partial unique index enforces a single active reservation per seat. 
- **Time handling:** Expiry checks rely on database time (via `SELECT now()`), not application wall clock.
- **Idempotency:** Repeat confirmations return the `CONFIRMED` reservation; repeat releases return the `CANCELLED` reservation.


## Future things to implement 
- Background job to mark stale `HELD` reservations as `EXPIRED`
- Idempotency keys for hold/confirm endpoints
- Pagination and filters for availability queries
- Authentication e.g., JWT and admin tooling
- Rate limiting 
- Docker Compose for Postgres for one-command spin-up
- Deployment targets using Render
