from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import secrets
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status, Cookie, Response
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import (
    ALLOWED_EMAIL_DOMAIN,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET_KEY,
    ENV,
    FRONTEND_AUTH_CALLBACK_URL,
    REFRESH_TOKEN_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.database import get_db
from app.models.user import User


router = APIRouter(tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _require_config() -> None:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth2 is not configured. Please set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET.",
        )


def _is_allowed_domain(email: str) -> bool:
    domain = (ALLOWED_EMAIL_DOMAIN or "").strip().lower()
    if not domain:
        return True
    return email.strip().lower().endswith(f"@{domain}")


def _create_access_token(*, user: User) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=int(JWT_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.full_name,
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _create_refresh_token(*, user: User) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub":  str(user.id),
        "type": "refresh",
        "exp":  now + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS)),
        "iat":  now,
    }
    return jwt.encode(payload, REFRESH_TOKEN_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    access_token_cookie: Optional[str] = Cookie(default=None, alias="access_token"),
) -> User:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif access_token_cookie:
        token = access_token_cookie

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(str(sub))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is deactivated.",
        )
    return user


@router.get("/auth/google/login")
async def google_login():
    _require_config()

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "include_granted_scopes": "true",
        "prompt": "select_account",
    }
    # CSRF protection: generate state, store in a cookie, and include in params
    state = secrets.token_urlsafe(32)
    params["state"] = state
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    response = RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    secure_flag = True if ENV == "prod" else False
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=60 * 5,  # short-lived state cookie (5 minutes)
        path="/",
    )
    return response


@router.get("/auth/google/callback")
async def google_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    oauth_state: Optional[str] = Cookie(default=None, alias="oauth_state"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_config()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'code' from Google.")

    # Verify OAuth2 state to prevent CSRF (login CSRF)
    if not state or not oauth_state or state != oauth_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or missing OAuth state.")

    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange code for token (status {token_resp.status_code}).",
            )
        token_json = token_resp.json()
        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing access_token from Google.")

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch Google userinfo (status {userinfo_resp.status_code}).",
            )
        info = userinfo_resp.json()

    email = (info.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account has no email.")

    if not _is_allowed_domain(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only @{ALLOWED_EMAIL_DOMAIN} emails are allowed.",
        )

    google_sub = info.get("sub")
    full_name = info.get("name")
    avatar_url = info.get("picture")

    now = datetime.now(timezone.utc)

    user: Optional[User] = None
    if google_sub:
        user = db.scalar(select(User).where(User.google_sub == google_sub))
    if not user:
        user = db.scalar(select(User).where(User.email == email))

    if not user:
        user = User(
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            google_sub=google_sub,
            is_active=True,
            last_login_at=now,
        )
        db.add(user)
    else:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is deactivated.",
            )
        user.email = email
        user.full_name = full_name
        user.avatar_url = avatar_url
        if google_sub:
            user.google_sub = google_sub
        user.last_login_at = now

    db.commit()
    db.refresh(user)

    access_token = _create_access_token(user=user)
    refresh_token = _create_refresh_token(user=user)

    response = RedirectResponse(url=FRONTEND_AUTH_CALLBACK_URL, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    # In production, require Secure; in dev allow insecure cookie for localhost
    secure_flag = True if ENV == "prod" else False
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=int(JWT_EXPIRE_MINUTES) * 60,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=int(REFRESH_TOKEN_EXPIRE_DAYS) * 24 * 60 * 60,
        path="/",
    )
    response.delete_cookie("oauth_state", path="/")
    return response


@router.post("/auth/refresh")
async def refresh_access_token(
    response: Response,
    refresh_token_cookie: Optional[str] = Cookie(default=None, alias="refresh_token"),
    db: Session = Depends(get_db),
):
    if not refresh_token_cookie:
        raise HTTPException(status_code=401, detail="Missing refresh token.")

    try:
        payload = jwt.decode(refresh_token_cookie, REFRESH_TOKEN_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired. Please log in again.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    user_id = UUID(str(payload.get("sub")))
    user = db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated.")

    new_access_token = _create_access_token(user=user)
    secure_flag = True if ENV == "prod" else False
    response.set_cookie(
        "access_token",
        new_access_token,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=int(JWT_EXPIRE_MINUTES) * 60,
        path="/",
    )
    return {"ok": True}


@router.get("/auth/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "avatar_url": current_user.avatar_url,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "last_login_at": current_user.last_login_at,
    }


@router.post("/auth/logout")
async def logout(response: Response):
    # Clear auth cookies on logout
    secure_flag = True if ENV == "prod" else False
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("oauth_state", path="/")
    return {"ok": True}
