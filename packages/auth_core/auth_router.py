import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from packages.auth_core.auth_service import (
    authenticate_user,
    change_user_password,
    create_access_token,
    get_user_by_username,
    register_dashboard_user,
)
from packages.auth_core.config import settings
from packages.auth_core.dependencies import admin_required, auth_required
from packages.auth_core.limiter import limiter

logger = logging.getLogger(__name__)

PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]).{8,}$'
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _session_cookie_samesite() -> str:
    """Cross-subdomain SPA (dashboard.onrender.com → api.onrender.com) needs SameSite=None."""
    return "none" if settings.COOKIE_SECURE else "lax"


class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Senha fraca. Exige: 8+ caracteres, maiúscula, minúscula, número e caractere especial."
            )
        return v

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Senha fraca. Exige: 8+ caracteres, maiúscula, minúscula, número e caractere especial."
            )
        return v

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, login_data: LoginRequest):
    """Processes login and sets a secure cookie."""
    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")

    token = create_access_token(
        data={"sub": user["username"]},
        role=user.get("role", "org_admin"),
        org_id=user.get("organization_id"),
        professional_id=user.get("professional_id"),
    )

    response = JSONResponse(content={"status": "success", "user": user["username"]})
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        max_age=3600 * 24,  # 24h
        samesite=_session_cookie_samesite(),
    )
    return response

@router.post("/logout")
async def logout():
    """Clears the session cookie."""
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(
        "session_token",
        secure=settings.COOKIE_SECURE,
        samesite=_session_cookie_samesite(),
    )
    return response

@router.post("/change-password", dependencies=[Depends(auth_required)])
@limiter.limit("3/minute")
async def change_password(request: Request, payload: ChangePasswordRequest, user: str = Depends(auth_required)):
    """Changes the password for the authenticated user."""
    user_data = get_user_by_username(user)
    if not user_data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Authenticate to verify current password
    if not authenticate_user(user, payload.current_password):
        raise HTTPException(status_code=401, detail="Senha atual incorreta.")

    success = change_user_password(user, payload.new_password)
    if success:
        logger.info(f"🔑 Password changed for user: {user}")
        return {"status": "success", "message": "Senha atualizada com sucesso."}
    else:
        raise HTTPException(status_code=500, detail="Erro interno ao atualizar senha.")

@router.post("/register", dependencies=[Depends(admin_required)])
@limiter.limit("3/minute")
async def register(request: Request, register_data: RegisterRequest):
    """Creates a new dashboard user. Restricted to super_admin."""
    if get_user_by_username(register_data.username):
        raise HTTPException(status_code=400, detail="Usuário já cadastrado.")

    success = register_dashboard_user(register_data.username, register_data.password)
    if success:
        return {"status": "success", "message": "Usuário criado com sucesso."}
    else:
        raise HTTPException(status_code=500, detail="Erro interno ao criar usuário.")

@router.get("/me", dependencies=[Depends(auth_required)])
async def get_current_user(user: str = Depends(auth_required)):
    """Returns the currently authenticated user based on the session token."""
    user_data = get_user_by_username(user)
    if not user_data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    org_id = user_data.get("organization_id")
    org_name = None
    if org_id:
        try:
            from packages.auth_core.database import db
            if db.is_ready:
                org_row = (
                    db.client.table("organizations")
                    .select("name")
                    .eq("id", org_id)
                    .maybe_single()
                    .execute()
                )
                if org_row.data:
                    org_name = org_row.data.get("name")
        except Exception as e:
            # Non-critical: org_name stays None and /me still returns. Log for debugging.
            logger.debug("Could not resolve organization name for org_id=%s: %s", org_id, e)

    return {
        "status": "success",
        "user": {
            "username": user_data["username"],
            "role": user_data.get("role", "org_admin"),
            "organization_id": org_id,
            "organization_name": org_name,
            "professional_id": user_data.get("professional_id"),
        }
    }
