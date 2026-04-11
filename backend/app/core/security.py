from fastapi import Depends, HTTPException, status, Header, Cookie
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository
from app.models.user import User, UserRole
from app.core.config import JWT_SECRET_KEY


def get_auth_service(db: Session = Depends(get_db)):
    return AuthService(UserRepository(db))


def get_current_user(
    service: AuthService = Depends(get_auth_service),
    authorization: str = Header(None, alias="Authorization"),
    access_token_cookie: str = Cookie(None, alias="access_token"),
) -> User:
    token = None

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif access_token_cookie:
        token = access_token_cookie

    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = service.decode_token(token, JWT_SECRET_KEY)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = service.user_repo.get_by_id(UUID(str(user_id)))

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return user

def require_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only",
        )
    return current_user