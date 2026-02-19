import os
from datetime import datetime, timedelta
from typing import Optional
import secrets

from fastapi import Depends, HTTPException, status, Request, Response
from passlib.context import CryptContext
from sqlmodel import Session, select
from pydantic import BaseModel

from database import get_session
from models import User, SessionData
from config import settings

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --- Session Management ---
SESSION_COOKIE_NAME = "session_id"
SESSION_EXPIRATION_MINUTES = 60 * 24 # 24 hours

class UserLogin(BaseModel):
    username: str
    password: str

async def create_user_session(response: Response, user_id: int, session: Session) -> str:
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=SESSION_EXPIRATION_MINUTES)
    session_data = SessionData(session_id=session_id, user_id=user_id, expires_at=expires_at)
    session.add(session_data)
    session.commit()
    session.refresh(session_data)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=True,  # Always secure in production (behind HTTPS proxy)
        expires=int(expires_at.timestamp())
    )
    return session_id

async def invalidate_user_session(response: Response, request: Request, session: Session):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        statement = select(SessionData).where(SessionData.session_id == session_id)
        db_session = session.exec(statement).first()
        if db_session:
            session.delete(db_session)
            session.commit()
    response.delete_cookie(SESSION_COOKIE_NAME)

async def get_current_user_optional(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    """Returns the current user or None if not authenticated (no exception)."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None

    statement = select(SessionData).where(SessionData.session_id == session_id)
    db_session_data = session.exec(statement).first()

    if not db_session_data or db_session_data.expires_at < datetime.utcnow():
        return None

    user = session.get(User, db_session_data.user_id)
    return user

async def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    statement = select(SessionData).where(SessionData.session_id == session_id)
    db_session_data = session.exec(statement).first()

    if not db_session_data or db_session_data.expires_at < datetime.utcnow():
        # Invalidate expired session if it still exists in cookie
        response = Response() # Need a response object to delete cookie
        response.delete_cookie(SESSION_COOKIE_NAME)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.get(User, db_session_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    # Add any checks for active user if needed, for now just returns the user
    return current_user

async def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an admin user",
        )
    return current_user
