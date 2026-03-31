from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
import httpx
import secrets
from urllib.parse import urlencode
from fastapi import HTTPException, status

from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.core.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES,
    REFRESH_TOKEN_SECRET_KEY, REFRESH_TOKEN_EXPIRE_DAYS,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ALLOWED_EMAIL_DOMAIN,
    GOOGLE_TOKEN_URL, GOOGLE_REDIRECT_URI, GOOGLE_USERINFO_URL, GOOGLE_AUTH_URL
)

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def require_config(self):
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google OAuth2 is not configured."
            )

    def is_allowed_domain(self, email: str) -> bool:
        domain = (ALLOWED_EMAIL_DOMAIN or "").strip().lower()
        if not domain: return True
        return email.strip().lower().endswith(f"@{domain}")

    def create_access_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=int(JWT_EXPIRE_MINUTES))
        payload = {
            "sub": str(user.id), "email": user.email, 
            "name": user.full_name, "exp": expire, "iat": datetime.now(timezone.utc)
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def create_refresh_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
        payload = {
            "sub": str(user.id), "type": "refresh", 
            "exp": expire, "iat": datetime.now(timezone.utc)
        }
        return jwt.encode(payload, REFRESH_TOKEN_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def decode_token(self, token: str, secret: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired.")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token.")

    async def get_google_user_info(self, code: str, redirect_uri: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            token_resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code, "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri, "grant_type": "authorization_code",
            })
            if token_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange Google code.")
            
            access_token = token_resp.json().get("access_token")
            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL, 
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return userinfo_resp.json()

    def sync_user(self, info: dict) -> User:
        email = (info.get("email") or "").strip()
        if not email or not self.is_allowed_domain(email):
            raise HTTPException(status_code=403, detail="Email domain not allowed.")

        google_sub = info.get("sub")
        user = self.user_repo.get_by_google_sub(google_sub) or self.user_repo.get_by_email(email)

        now = datetime.now(timezone.utc)
        if not user:
            user = User(
                email=email, full_name=info.get("name"), 
                avatar_url=info.get("picture"), google_sub=google_sub,
                is_active=True, last_login_at=now
            )
            return self.user_repo.create(user)
        
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User is deactivated.")
            
        user.full_name = info.get("name")
        user.avatar_url = info.get("picture")
        user.last_login_at = now
        self.user_repo.update()
        return user
    
    def generate_google_login_data(self) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        return state, self.build_google_login_url(state)

    def build_google_login_url(self, state: str) -> str:
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "include_granted_scopes": "true", # Giữ nguyên params của bạn
            "prompt": "select_account",
            "state": state
        }
        url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        return url
    