import bcrypt
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone

from app.config import settings
from fastapi import Depends
from app.database import get_db
from app.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def verify_password(plain : str, hashed: str):
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
        raise HTTPException(status_code=401, detail = "Invalid token", headers ={"WWW-Authenticate": "Bearer"})

def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    credentials_error = HTTPException(
        status_code = 401,
        detail = "Could not validate credentials",
        headers ={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_error
    return user


