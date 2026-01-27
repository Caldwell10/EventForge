"""
Helper functions for tests
"""

def make_user(client, name="Alice", email="alice@example.com", phone="0712345678", pwd="secret123"):
    resp = client.post("/users/", json={
        "name": name,
        "phone_number": phone,
        "email": email,
        "password": pwd,
    })
    assert resp.status_code == 200
    return resp.json()

def login(client, email: str, pwd: str):
    resp = client.post("/login", json={"email": email, "password": pwd})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def make_show(client, title="Rock Night", venue="Arena", starts_at="2030-01-01T20:00:00Z", headers=None):
    resp = client.post("/shows/", json={
        "title": title,
        "venue": venue,
        "starts_at": starts_at
    }, headers=headers)
    assert resp.status_code == 200
    return resp.json()

def add_seats(client, show_id: int, labels: list[str], headers=None):
    resp = client.post(f"/shows/{show_id}/seats", json={"seat_numbers": labels}, headers=headers)
    return resp

def hold(client, show_id: int, seat_label: str, minutes: int = 10, headers=None):
    return client.post("/reservations/hold", json={
        "seat_number": seat_label,
        "show_id": show_id,
        "hold_minutes": minutes
    }, headers=headers)

def confirm_reservation(client, reservation_id: int, headers=None):
    return client.post(f"/reservations/{reservation_id}/confirm", headers=headers)
