from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from user_service import auth, models, schemas
from user_service.database import get_db

router = APIRouter()


@router.post("/register", response_model=schemas.UserRegistrationResponse)
def register_user(payload: schemas.UserRegistrationRequest, db: Session = Depends(get_db)):
    # Проверяем, что username/email ещё не заняты
    existing_user = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    existing_email = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Хэшируем пароль
    hashed_pass = auth.get_password_hash(payload.password)

    # Создаём пользователя
    new_user = models.User(
        username=payload.username,
        password_hash=hashed_pass,
        email=payload.email,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return schemas.UserRegistrationResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        created_at=new_user.created_at
    )


@router.post("/login", response_model=schemas.UserLoginResponse)
def login(payload: schemas.UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = auth.create_access_token({"sub": str(user.id)})
    return schemas.UserLoginResponse(access_token=token)


@router.get("/profile", response_model=schemas.UserProfileResponse)
def get_profile(token: str = Depends(), db: Session = Depends(get_db)):
    # Здесь предполагается, что токен придёт через Header (Authorization Bearer ...)
    # либо query, если упростить. Нужно написать отдельный Depends для извлечения.
    try:
        payload = auth.decode_token(token)
        user_id = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return schemas.UserProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        birth_date=user.birth_date,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


@router.put("/profile", response_model=schemas.UserProfileResponse)
def update_profile(update_data: schemas.UserProfileUpdateRequest, token: str = Depends(),
                   db: Session = Depends(get_db)):
    # Аналогично извлекаем user_id из токена
    try:
        payload = auth.decode_token(token)
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем поля, если переданы
    if update_data.first_name is not None:
        user.first_name = update_data.first_name
    if update_data.last_name is not None:
        user.last_name = update_data.last_name
    if update_data.birth_date is not None:
        user.birth_date = update_data.birth_date
    if update_data.phone is not None:
        user.phone = update_data.phone

    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    return schemas.UserProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        birth_date=user.birth_date,
        created_at=user.created_at,
        updated_at=user.updated_at
    )