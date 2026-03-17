from fastapi import APIRouter, Depends, Cookie, Response, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.core.config import FRONTEND_AUTH_CALLBACK_URL, ENV

router = APIRouter(prefix="/auth", tags=["auth"])

def get_auth_service(db: Session = Depends(get_db)):
    repo = UserRepository(db)
    return AuthService(repo)

@router.get("/google/callback")
async def google_callback(
    code: str, 
    response: Response,
    service: AuthService = Depends(get_auth_service)
):
    try:
        google_info = await service.verify_google_code(code)
        user = service.sync_user(google_info)
        
        access_token = service.create_access_token(user)
        refresh_token = service.create_refresh_token(user)

        res = RedirectResponse(url=FRONTEND_AUTH_CALLBACK_URL)
        secure = (ENV == "prod")
        res.set_cookie("access_token", access_token, httponly=True, secure=secure)
        res.set_cookie("refresh_token", refresh_token, httponly=True, secure=secure)
        return res
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"ok": True}