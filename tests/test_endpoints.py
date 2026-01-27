from sqlalchemy import select, func
from app.models import Seat, Reservation
from helpers import add_seats, make_show, make_user, hold, confirm_reservation, login
from datetime import datetime, timezone
from conftest import client, db_session

def test_create_show_and_bulk_seats_normalizes_and_blocks_duplicates(client):
    user = make_user(client)
    headers = login(client, email=user["email"], pwd="secret123")
    show = make_show(client, headers=headers)

    # Add seats with mixed case and spaces
    resp = add_seats(client, show_id=show["id"], labels=["A1", "B2", " c5 "], headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    seat_numbers = sorted([seat["seat_number"] for seat in body])
    assert seat_numbers == ["A1", "B2", "C5"]  # norrmalized

    # try to add duplicate seats in a second call
    resp_dup = add_seats(client, show_id=show["id"], labels=["A1"], headers=headers)
    assert resp_dup.status_code in (400, 409)

def test_list_seat_availability(client, db_session):
    user = make_user(client)
    headers = login(client, email=user["email"], pwd="secret123")
    show = make_show(client, headers=headers)
    add_seats(client, show["id"], ["A1"], headers=headers)

    #Hold A1
    resp = hold(client, show_id=show["id"], seat_label="A1", minutes=5, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HELD"
    assert data["seat_id"] > 0

    # hold_expiry should be in the future relative to DB now()
    now_db = db_session.scalar(select(func.now()))
    from datetime import datetime, timezone
    expiry = datetime.fromisoformat(data["hold_expiry"].replace("Z", "+00:00"))
    assert expiry.tzinfo is not None
    assert expiry > now_db.replace(tzinfo=expiry.tzinfo)

def test_hold_seat_success(client, db_session):
    user = make_user(client)
    headers = login(client, email=user["email"], pwd="secret123")
    show = make_show(client, headers=headers)
    add_seats(client, show["id"], ["A1"], headers=headers)

    # Hold A1
    resp = hold(client, show_id=show["id"], seat_label="A1", minutes=5, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HELD"
    assert data["seat_id"] > 0
    # hold_expiry should be in the future relative to DB now()
    now_db = db_session.scalar(select(func.now()))
    from datetime import datetime, timezone
    expiry = datetime.fromisoformat(data["hold_expiry"].replace("Z", "+00:00"))
    assert expiry.tzinfo is not None
    assert expiry > now_db.replace(tzinfo=expiry.tzinfo)

def test_hold_same_seat_conflict(client):
    user = make_user(client, name="Bob", email="bob@example.com")
    headers = login(client, email=user["email"], pwd="secret123")
    show = make_show(client, title="Jazz Night", headers=headers)
    add_seats(client, show["id"], ["B1"], headers=headers)

    # First hold succeeds
    r1 = hold(client, show_id=show["id"], seat_label="B1", minutes=5, headers=headers)
    assert r1.status_code == 200

    # Second hold (same seat) should fail with 409 (active HELD blocks it)
    r2 = hold(client, show_id=show["id"], seat_label="B1", minutes=5, headers=headers)
    assert r2.status_code in (409, 400)

def test_confirm_success_and_expired_path(client, db_session):
    user = make_user(client, name="Cara", email="cara@example.com")
    headers = login(client, email=user["email"], pwd="secret123")
    show = make_show(client, title="Symphony", headers=headers)
    add_seats(client, show["id"], ["C1"], headers=headers)

    # Hold for 10 minutes
    r = hold(client, show_id=show["id"], seat_label="C1", minutes=10, headers=headers)
    assert r.status_code == 200
    res = r.json()
    res_id = res["id"]

    # Confirm should succeed
    c = confirm_reservation(client, res_id, headers=headers)
    assert c.status_code == 200
    assert c.json()["status"] == "CONFIRMED"

    # Make another hold, then force-expire it by setting hold_expiry in the past
    r2 = hold(client, show_id=show["id"], seat_label="C1", minutes=1, headers=headers)
    # This second hold should actually fail because seat is CONFIRMED already (unique partial index),
    # but let's demonstrate expiry on a different seat:
    add_seats(client, show["id"], ["C2"], headers=headers)
    r3 = hold(client, show_id=show["id"], seat_label="C2", minutes=1, headers=headers)
    assert r3.status_code == 200
    res2 = r3.json()
    res2_id = res2["id"]

    # Force expire via DB
    past = db_session.scalar(select(func.now()))  # current DB time
    db_session.query(Reservation).filter(Reservation.id == res2_id).update(
        {Reservation.hold_expiry: past}  # set expiry to now (== expired)
    )
    db_session.commit()

    # Confirm should now 400 and flip to EXPIRED in your endpoint code
    c2 = confirm(client, res2_id)
    assert c2.status_code == 400
    # optional: re-read to assert EXPIRED
    expired = db_session.get(Reservation, res2_id)
    assert expired.status == "EXPIRED"




