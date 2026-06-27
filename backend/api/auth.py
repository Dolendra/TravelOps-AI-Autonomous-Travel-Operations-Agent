from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.database.models import UserModel
from backend.services.auth import SecurityService
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class UserRegisterInput(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Optional[str] = "passenger"

class UserLoginInput(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshInput(BaseModel):
    refresh_token: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: UserRegisterInput, db: Session = Depends(get_db)):
    # 1. Check if role is valid
    if data.role not in ["admin", "operator", "passenger"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'admin', 'operator', or 'passenger'."
        )
        
    # 2. Check if user already exists
    existing = db.query(UserModel).filter(UserModel.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )

    # 3. Create user
    hashed = SecurityService.hash_password(data.password)
    user = UserModel(
        email=data.email,
        password_hash=hashed,
        name=data.name,
        role=data.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"success": True, "message": f"User {user.name} registered successfully."}

@router.post("/login", response_model=TokenResponse)
def login(data: UserLoginInput, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == data.email).first()
    if not user or not SecurityService.verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Issue tokens
    token_data = {"sub": user.email, "id": user.id, "role": user.role}
    access_token = SecurityService.create_access_token(token_data)
    refresh_token = SecurityService.create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh")
def refresh(data: RefreshInput, db: Session = Depends(get_db)):
    payload = SecurityService.decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )
        
    user_id = payload.get("id")
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found."
        )

    new_token_data = {"sub": user.email, "id": user.id, "role": user.role}
    new_access_token = SecurityService.create_access_token(new_token_data)
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

# FastAPI Dependencies

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserModel:
    payload = SecurityService.decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload schema.",
        )
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token does not exist.",
        )
    return user

def require_role(required_role: str):
    def dependency(current_user: UserModel = Depends(get_current_user)):
        # Admin can do anything
        if current_user.role == "admin":
            return current_user
        # Operator has access to operator and passenger commands
        if required_role == "operator" and current_user.role in ["admin", "operator"]:
            return current_user
        # Passenger has baseline access
        if required_role == current_user.role:
            return current_user
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient role privileges."
        )
    return dependency
