import contextvars
from contextlib import contextmanager
from typing import Any

# Context variables to store the current tenant ID and user role
current_org_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_org_id", default=None)
user_role: contextvars.ContextVar[str] = contextvars.ContextVar("user_role", default="org_admin")

@contextmanager
def set_tenant_context(org_id: str, role: str = "org_admin"):
    """
    Context manager to set the tenant context for the current request/block.
    """
    org_token = current_org_id.set(org_id)
    role_token = user_role.set(role)
    try:
        yield
    finally:
        current_org_id.reset(org_token)
        user_role.reset(role_token)

def get_tenant_context() -> dict[str, Any]:
    """Returns the current tenant ID and user role."""
    return {
        "org_id": current_org_id.get(),
        "role": user_role.get()
    }

def get_current_org_id() -> str | None:
    """Helper to get just the current organization ID."""
    return current_org_id.get()
