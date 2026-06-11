import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from packages.auth_core.config import settings
from packages.auth_core.database import db
from packages.auth_core.dependencies import ALGORITHM, SECRET_KEY

logger = logging.getLogger(__name__)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its hash using direct bcrypt."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
    role: str = "org_admin",
    org_id: str | None = None,
    professional_id: str | None = None,
) -> str:
    """Creates a JWT access token with embedded role, org and (optional) professional context."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    # Uses setting directly instead of local constant
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode.update({"exp": expire, "iat": now, "role": role})
    if org_id:
        to_encode["org_id"] = org_id
    if professional_id:
        to_encode["professional_id"] = professional_id

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user_by_username(username: str):
    """Fetches a user from Supabase by email."""
    try:
        res = db.client.table("dashboard_users").select("*").eq("email", username).execute()
        if res.data:
            user_data = res.data[0]
            return {
                "username": user_data["email"],
                "role": user_data.get("role", "org_admin"),
                "organization_id": user_data.get("organization_id"),
                "professional_id": user_data.get("professional_id"),
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching user {username}: {e}")
        return None

def authenticate_user(username: str, password: str):
    """Authenticates a user using Supabase Auth and returns profile if successful."""
    try:
        import httpx

        from packages.auth_core.config import settings
        from supabase import ClientOptions, create_client

        http_client = httpx.Client(http2=False, timeout=10.0)
        temp_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY,
            options=ClientOptions(httpx_client=http_client)
        )

        auth_response = temp_client.auth.sign_in_with_password({"email": username, "password": password})
        if not auth_response.user:
            return False

        return get_user_by_username(username)
    except Exception as e:
        logger.error(f"Authentication failed for {username}: {e}")
        return False

def change_user_password(username: str, new_password: str) -> bool:
    """Updates the user's password in Supabase Auth using Admin API."""
    try:
        user_data = get_user_by_username(username)
        if not user_data:
            return False

        res = db.client.table("dashboard_users").select("id").eq("email", username).execute()
        if not res.data:
            return False
        user_id = res.data[0]["id"]

        db.client.auth.admin.update_user_by_id(user_id, {"password": new_password})
        return True
    except Exception as e:
        logger.error(f"Error changing password for {username}: {e}")
        return False

def register_dashboard_user(
    username: str,
    password: str,
    role: str = "super_admin",
    organization_id: str | None = None,
) -> bool:
    """Creates a new user in Supabase Auth and dashboard_users."""
    try:
        auth_res = db.client.auth.admin.create_user({
            "email": username,
            "password": password,
            "email_confirm": True
        })
        if not auth_res.user:
            return False

        new_user = {
            "id": auth_res.user.id,
            "email": username,
            "role": role,
        }
        if organization_id:
            new_user["organization_id"] = organization_id
        db.client.table("dashboard_users").insert(new_user).execute()
        return True
    except Exception as e:
        logger.error(f"Error registering user {username}: {e}")
        return False
