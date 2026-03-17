from datetime import datetime, timezone, timedelta
from jose import jwt
import httpx
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.core.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES,
    REFRESH_TOKEN_SECRET_KEY, REFRESH_TOKEN_EXPIRE_DAYS,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    ALLOWED_EMAIL_DOMAIN
)

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def create_access_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=int(JWT_EXPIRE_MINUTES))
        payload = {"sub": str(user.id), "email": user.email, "exp": expire}
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def create_refresh_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
        payload = {"sub": str(user.id), "type": "refresh", "exp": expire}
        return jwt.encode(payload, REFRESH_TOKEN_SECRET_KEY, algorithm=JWT_ALGORITHM)

    async def verify_google_code(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            # Đổi code lấy token
            token_resp = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI, "grant_type": "authorization_code",
            })
            token_data = token_resp.json()
            
            # Lấy thông tin user
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )
            return userinfo_resp.json()

    def sync_user(self, google_info: dict) -> User:
        email = google_info.get("email")
        if not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
            raise ValueError(f"Chỉ chấp nhận email @{ALLOWED_EMAIL_DOMAIN}")

        user = self.user_repo.get_by_google_sub(google_info.get("sub"))
        if not user:
            user = self.user_repo.get_by_email(email)

        now = datetime.now(timezone.utc)
        if not user:
            user = User(
                email=email,
                full_name=google_info.get("name"),
                avatar_url=google_info.get("picture"),
                google_sub=google_info.get("sub"),
                last_login_at=now
            )
            return self.user_repo.create(user)
        
        user.last_login_at = now
        self.user_repo.update()
        return user