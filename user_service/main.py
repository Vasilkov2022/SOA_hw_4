from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import uvicorn
from passlib.hash import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from common.kafka import send

import models
import schemas
from database import engine, SessionLocal, Base

SECRET_KEY = os.getenv("SECRET_KEY", "MY_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="User Service",
    version="1.0.0"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        login: str = payload.get("sub")
        if login is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.login == login).first()
    if user is None:
        raise credentials_exception
    return user

@app.post("/users/register", response_model=schemas.UserOut)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    user_exist = db.query(models.User).filter(
        (models.User.login == user_in.login) | (models.User.email == user_in.email)
    ).first()
    if user_exist:
        raise HTTPException(status_code=400, detail="Login or email already registered")

    hashed_password = bcrypt.hash(user_in.password)
    user = models.User(
        login=user_in.login,
        password=hashed_password,
        email=user_in.email
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    send("user-registrations", {
        "user_db": user.id,
        "registered_at": user.created_at.isoformat(),
    })
    return user

@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.login == form_data.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect login or password")
    if not bcrypt.verify(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect login or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.login}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.UserOut)
def get_my_profile(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.put("/users/me", response_model=schemas.UserOut)
def update_my_profile(
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if user_update.first_name is not None:
        current_user.first_name = user_update.first_name
    if user_update.last_name is not None:
        current_user.last_name = user_update.last_name
    if user_update.date_of_birth is not None:
        current_user.date_of_birth = user_update.date_of_birth
    if user_update.phone_number is not None:
        current_user.phone_number = user_update.phone_number
    if user_update.email is not None:
        email_exists = db.query(models.User).filter(
            models.User.email == user_update.email,
            models.User.id != current_user.id
        ).first()
        if email_exists:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = user_update.email

    db.commit()
    db.refresh(current_user)
    return current_user



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)