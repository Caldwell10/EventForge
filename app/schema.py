from pydantic import BaseModel, EmailStr, Field, conlist, conint
from datetime import datetime
from typing import Literal

# User Schemas
class UserCreate(BaseModel):
    name: str
    phone_number: str = Field(min_length=9)
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    phone_number: str
    email: EmailStr

    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str # holds signed JWT
    token_type: str = "bearer"

# Show Schemas
class ShowCreate(BaseModel):
    title: str
    venue: str
    starts_at: datetime

class ShowOut(BaseModel):
    id: int
    title: str
    venue: str
    starts_at: datetime

    class Config:
        orm_mode = True

# Seat Schemas
class SeatCreateBulk(BaseModel):
    seat_numbers: conlist(str, min_length=1) 

class SeatOut(BaseModel):
    id: int
    show_id: int
    seat_number: str
    
    class Config:
        orm_mode = True

class SeatAvailabilityOut(BaseModel):
    seat_id: str
    seat_number: str
    status: Literal["AVAILABLE", "HELD", "RESERVED"]
    hold_expiry: datetime | None = None

    class Config:
        orm_mode = True


# Reservation Schemas
class ReservationCreate(BaseModel):
    seat_number: str
    show_id: int
    hold_minutes: conint(gt=0, le=20)= 10

class ReservationOut(BaseModel):
    id: int
    user_id: int
    seat_id: int
    status: Literal["HELD", "CONFIRMED", "EXPIRED", "CANCELLED"]
    hold_expiry: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

