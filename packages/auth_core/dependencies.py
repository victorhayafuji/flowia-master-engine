"""
Centralized FastAPI dependencies for authentication, database access, and tenant context.
All route files MUST import from here — no more copy-pasting.
"""
import logging
import re

import jwt
from fastapi import Header, HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader

from packages.auth_core.config import settings

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)

# JWT constants (kept here to avoid circular imports with auth service)
SECRET_KEY = settings.DASHBOARD_JWT_SECRET
ALGORITHM = "HS256"

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def _decode_session_token(token: str) -> dict | None:
    """Decodes a JWT session token and returns the full payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub"):
            return payload
    except jwt.ExpiredSignatureError:
        logger.warning("🕒 Session token expired")
    except jwt.PyJWTError:
        logger.warning("🔑 Invalid JWT signature")
    except Exception as e:
        logger.error(f"❌ Auth error: {str(e)}")
    return None


async def auth_required(
    request: Request,
    api_key: str = Security(api_key_header)
):
    """
    Validates either a secure session cookie (Browser) or an API Key (Programmatic).
    Returns the username of the authenticated user.
    """
    token = request.cookies.get("session_token")
    if token:
        payload = _decode_session_token(token)
        if payload:
            return payload.get("sub")

    if api_key and api_key == settings.DASHBOARD_API_KEY:
        return "api_user"

    logger.error(f"🚫 Unauthorized access attempt to {request.url.path}. Cookie present: {'Yes' if token else 'No'}")
    raise HTTPException(
        status_code=401,
        detail="Autenticação necessária. Faça login no painel."
    )


async def admin_required(
    request: Request,
    api_key: str = Security(api_key_header)
):
    """
    Restricts access to super_admin users only.
    API Key users are treated as admins (server-to-server trust).
    """
    token = request.cookies.get("session_token")
    if token:
        payload = _decode_session_token(token)
        if payload:
            role = payload.get("role", "")
            if role == "super_admin":
                return payload.get("sub")
            logger.warning(f"🚫 Non-admin user '{payload.get('sub')}' attempted admin action on {request.url.path}")
            raise HTTPException(
                status_code=403,
                detail="Permissão insuficiente. Acesso restrito a administradores."
            )

    if api_key and api_key == settings.DASHBOARD_API_KEY:
        return "api_user"

    raise HTTPException(
        status_code=401,
        detail="Autenticação necessária. Faça login no painel."
    )


def _is_valid_org_header(org_id: str) -> bool:
    return org_id == "ALL" or bool(_UUID_PATTERN.match(org_id))


async def validated_tenant_context(
    request: Request,
    x_organization_id: str = Header(..., alias="x-organization-id"),
    api_key: str = Security(api_key_header),
) -> str:
    """
    Validates x-organization-id against the authenticated user's JWT org_id.
    super_admin may use ALL or any org; other roles must match their JWT org_id.
    API key users are trusted for server-to-server calls.
    """
    org_id = x_organization_id.strip()

    if not _is_valid_org_header(org_id):
        raise HTTPException(
            status_code=400,
            detail="x-organization-id inválido. Use um UUID ou ALL.",
        )

    if api_key and api_key == settings.DASHBOARD_API_KEY:
        return org_id

    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária. Faça login no painel.",
        )

    payload = _decode_session_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Sessão inválida ou expirada.",
        )

    role = payload.get("role", "org_admin")
    jwt_org_id = payload.get("org_id")

    if role == "super_admin":
        return org_id

    if org_id == "ALL":
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito. Apenas super_admin pode usar ALL.",
        )

    if not jwt_org_id:
        raise HTTPException(
            status_code=403,
            detail="Usuário sem organização vinculada.",
        )

    if org_id != jwt_org_id:
        logger.warning(
            "Tenant spoof attempt: user=%s header=%s jwt=%s",
            payload.get("sub"),
            org_id,
            jwt_org_id,
        )
        raise HTTPException(
            status_code=403,
            detail="Organização não autorizada para este usuário.",
        )

    return org_id


# Backward-compatible alias — all routes should use validated_tenant_context
tenant_context = validated_tenant_context


async def professional_scope(
    request: Request,
    api_key: str = Security(api_key_header),
) -> str | None:
    """
    Returns the professional_id a user is restricted to (role 'professional'),
    or None for full org access (org_admin, super_admin, API key).
    Routes use this to scope an employee to their own agenda.
    """
    if api_key and api_key == settings.DASHBOARD_API_KEY:
        return None

    token = request.cookies.get("session_token")
    if not token:
        return None

    payload = _decode_session_token(token)
    if not payload:
        return None

    if payload.get("role") == "professional":
        return payload.get("professional_id")
    return None


def get_db():
    """Returns the singleton SupabaseHandler instance."""
    from packages.auth_core.database import SupabaseHandler
    return SupabaseHandler()
