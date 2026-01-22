import uvicorn

from datetime import timedelta
from fastapi import FastAPI, HTTPException, Depends
from app.schema import UserCreate, UserOut, ShowCreate, ShowOut, SeatCreateBulk, SeatOut, ReservationCreate, ReservationOut, UserLogin, Token
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.models import User, Show, Seat, Reservation
from app.database import get_db
from app.services import hash_password, normalize_seat_labels, calculate_hold_expiry
from app.auth import verify_password, create_access_token
from app.config import settings

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Event Ticketing System API"}

@app.post("/users/", response_model=UserOut)
def create_user(user: UserCreate, db=Depends(get_db)):
    """Create the user endpoint"""
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    new_user = User(
        name = user.name,
        phone_number = user.phone_number,
        email = user.email,
        password = hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@app.post("/login", response_model=Token)
def login(user: UserLogin, db = Depends(get_db)):
    curr_user = db.query(User).filter(User.email == user.email).first()
    if not curr_user or verify_password(user.password, curr_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(
        {"sub": curr_user.id, "email": curr_user.email},
        timedelta(minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/shows/", response_model=ShowOut)
def create_show(show: ShowCreate, db=Depends(get_db)):
    """ create show endpoint"""
    existing_show = db.query(Show).filter(Show.title == show.title, Show.starts_at == show.starts_at).first()
    if existing_show:
        raise HTTPException(status_code=400, detail="Show with the same title and start time already exists")
    
    new_show = Show(**show.dict())

    db.add(new_show)
    db.commit()
    db.flush(new_show)

    return new_show

@app.post("/shows/{show_id}/seats", response_model=list[SeatOut])
def create_seats_bulk(show_id: int, seats: SeatCreateBulk, db=Depends(get_db)):
    """Bulk create seats endpoint"""
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    
    # normalize seat labels and dedupe labels in the request
    try:
        normalized_labels = [normalize_seat_labels(s) for s in seats.seat_numbers]
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    
    # check for seat duplicates
    if len(normalized_labels) != len(set(normalized_labels)):
        raise HTTPException(status_code=400, detail="Duplicate seat labels in request")

    new_seats = [Seat(show_id = show_id, seat_number=labels) for labels in normalized_labels]

    # Bulk save seats into database and handle potential integrity errors
    db.add_all(new_seats)
    try: 
        db.flush()  # populate new_seats with IDs
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="One or more seat labels already exist for this show")
    
    db.commit()

    return new_seats

@app.get("/shows/{show_id}/seats", response_model=list[SeatOut])
def get_seats_for_show(show_id: int, db=Depends(get_db)):
    """create seats for a show"""
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    
    # fetch seats for the show
    seats = db.query(Seat).filter(Seat.show_id == show_id).all()
    return seats

# reservation endpoints
@app.post("/reservations/{user_id}/hold", response_model=ReservationOut)
def hold_seat_reservation(user_id: int, reservation: ReservationCreate, db=Depends(get_db)):
    # check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # check if show exists
    show = db.query(Show).filter(Show.id == reservation.show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    
    # check if seat exists for the show
    seat_label = normalize_seat_labels(reservation.seat_number)
    seat = db.query(Seat).filter(Seat.show_id == reservation.show_id, Seat.seat_number == seat_label).first()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found for the specified show")
    
    # create reservation with hold status "HELD"
    new_reservation = Reservation(
        user_id = user_id,
        seat_id = seat.id,
        status = "HELD",
        hold_expiry = calculate_hold_expiry(reservation.hold_minutes),
    )

    db.add(new_reservation)
    try:
        db.flush()  # populate new_reservation with ID
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Seat is already reserved")
    
    # if flush is successful, commit the transaction
    db.commit()
    db.refresh(new_reservation)

    return new_reservation

@app.post("/reservations/{reservation_id}/confirm", response_model=ReservationOut)
def confirm_seat_reservation(reservation_id: int, db=Depends(get_db)):
    # Lock reservation row to avoid two concurrent confirmations
    reservation = db.query(Reservation).filter(Reservation.id ==reservation_id).with_for_update().first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    if reservation.status == "CONFIRMED":
       return reservation
    
    # check if reservation has expired
    if reservation.status != "HELD":
        raise HTTPException(status_code=400, detail=f"Cannot confirm a reservation with status {reservation.status}")
    
    now_db = db.scalar(select(func.now()))
    if reservation.hold_expiry <= now_db:
        reservation.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=400, detail="Reservation has expired")

    reservation.status = "CONFIRMED"
    try:
        db.commit() 
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Seat is already reserved")

    db.refresh(reservation)
    return reservation

@app.post("/reservations/{reservation_id}/release", response_model=ReservationOut)
def release_seat_reservation(reservation_id: int, db=Depends(get_db)):
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).with_for_update().first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    if reservation.status == "CANCELLED":
        return reservation
    
    if reservation.status != "HELD":
        raise HTTPException(status_code=400, detail=f"Cannot cancel a reservation with status {reservation.status}")
    
    # cancel reservation
    reservation.status = "CANCELLED"

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to cancel reservation due to a server error")
    
    db.refresh(reservation)

    return reservation

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001) 