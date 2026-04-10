import secrets
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, Header, HTTPException, status, Cookie, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.security import get_current_user
from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.models.user import User
from app.core.config import (
    ENV, FRONTEND_AUTH_CALLBACK_URL, GOOGLE_AUTH_URL, 
    GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI, JWT_SECRET_KEY, 
    REFRESH_TOKEN_SECRET_KEY, JWT_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
)

router = APIRouter(prefix="/auth", tags=["auth"])

def get_auth_service(db: Session = Depends(get_db)):
    return AuthService(UserRepository(db))

# --- DEPENDENCY: GET_CURRENT_USER ---
# async def get_current_user(
#     service: AuthService = Depends(get_auth_service),
#     authorization: str = Header(None, alias="Authorization"),
#     access_token_cookie: str = Cookie(None, alias="access_token"),
# ) -> User:
#     token = None
#     if authorization and authorization.lower().startswith("bearer "):
#         token = authorization.split(" ", 1)[1].strip()
#     elif access_token_cookie:
#         token = access_token_cookie

#     if not token:
#         raise HTTPException(status_code=401, detail="Missing token.")
    
#     payload = service.decode_token(token, JWT_SECRET_KEY)
#     user_id = UUID(str(payload.get("sub")))
#     user = service.user_repo.get_by_id(user_id)
    
#     if not user or not user.is_active:
#         raise HTTPException(status_code=401, detail="User not found or inactive.")
#     return user

# --- ROUTES ---

@router.get("/google/login", summary="Khởi tạo đăng nhập Google")
async def google_login(
    oauth_state: str = Cookie(None, alias="oauth_state"),
    service: AuthService = Depends(get_auth_service),
):
    # 1. Gọi service để kiểm tra config và lấy dữ liệu (state, url)
    service.require_config()
    if oauth_state:
        state = oauth_state
        login_url = service.build_google_login_url(state)
    else:
        state, login_url = service.generate_google_login_data()

    # 2. Tạo RedirectResponse với status code 307 (Yêu cầu của bạn)
    response = RedirectResponse(
        url=login_url, 
        status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )

    # 3. Set cookie với đầy đủ 7 trường bảo mật như file gốc
    secure_flag = True if ENV == "prod" else False
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,        # Chống XSS
        secure=secure_flag,   # Chỉ gửi qua HTTPS trong prod
        samesite="lax",       # Chống CSRF
        max_age=60 * 5,       # 5 phút
        path="/",             # Hiệu lực toàn domain
    )
    
    return response

@router.get("/google/callback")
async def google_callback(
    code: str = None, state: str = None,
    oauth_state: str = Cookie(None, alias="oauth_state"),
    service: AuthService = Depends(get_auth_service)
):
    service.require_config()
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")
    if not state or not oauth_state:
        raise HTTPException(status_code=400, detail="Missing OAuth state.")
    if not secrets.compare_digest(state, oauth_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")

    info = await service.get_google_user_info(code, GOOGLE_REDIRECT_URI)
    user = service.sync_user(info)

    access_token = service.create_access_token(user)
    refresh_token = service.create_refresh_token(user)

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

@router.post("/refresh")
async def refresh_access_token(
    response: Response,
    refresh_token: str = Cookie(None, alias="refresh_token"),
    service: AuthService = Depends(get_auth_service)
):
    if not refresh_token: raise HTTPException(status_code=401, detail="Missing refresh token.")
    
    payload = service.decode_token(refresh_token, REFRESH_TOKEN_SECRET_KEY)
    if payload.get("type") != "refresh": raise HTTPException(status_code=401, detail="Invalid token type.")

    user = service.user_repo.get_by_id(UUID(str(payload.get("sub"))))
    if not user or not user.is_active: raise HTTPException(status_code=401, detail="User inactive.")

    new_access = service.create_access_token(user)
    response.set_cookie("access_token", new_access, httponly=True, secure=(ENV == "prod"), samesite="lax")
    return {"ok": True}

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "avatar_url": current_user.avatar_url,
        "role": current_user.role,
        "created_at": current_user.created_at,
        "last_login_at": current_user.last_login_at,
    }

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}