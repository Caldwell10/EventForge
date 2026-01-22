import bcrypt
from services import hash_password
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi import HTTPException
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from app.config import Settings
from fastapi import Depends
from app.database import get_db

settings = Settings()

oauth2_scheme = OAuth2AuthorizationCodeBearer(tokenUrl="/login")

def verify_password(plain, hashed):
    hashed = hash_password(hashed)
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy() 
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire}) # add JWT expiration claim into payload
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail = "Invalid token")


def get_current_user(user, db = Depends(get_db)):