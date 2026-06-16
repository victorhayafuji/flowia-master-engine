"""Shared helpers for catalog routers."""
from __future__ import annotations

from packages.auth_core.database import SupabaseHandler
from packages.auth_core.exceptions import BusinessLogicError
from packages.models.enums import Vertical

MVP_ALLOWED_VERTICAL = Vertical.SALON

PRODUCT_LINE_VERTICALS: dict[str, list[str]] = {
    "salon": [Vertical.SALON.value],
    "clinic": [Vertical.DENTAL.value, Vertical.MEDICAL.value],
}


def sync_service_professionals(
    db: SupabaseHandler, org_id: str, service_id: str, professional_ids: list
) -> None:
    """Replaces the eligibility set (which professionals can perform a service)."""
    del_query = db.client.table("service_professionals").delete().eq("service_id", service_id)
    if org_id and org_id != "ALL":
        del_query = del_query.eq("organization_id", org_id)
    del_query.execute()

    if professional_ids:
        rows = [
            {
                "organization_id": org_id,
                "service_id": service_id,
                "professional_id": str(pid),
            }
            for pid in professional_ids
        ]
        db.client.table("service_professionals").insert(rows).execute()


def verticals_for_product_line(product_line: str) -> list[str]:
    return PRODUCT_LINE_VERTICALS.get(product_line, [product_line])


def mask_secret(value: str | None) -> str | None:
    """Returns a masked preview (last 4 chars) of a secret, never the raw value."""
    token = (value or "").strip()
    if not token:
        return None
    if len(token) <= 4:
        return "••••"
    return f"••••{token[-4:]}"


def raise_on_whatsapp_phone_conflict(exc: Exception) -> None:
    err = str(exc).lower()
    if "23505" in err or "duplicate" in err or "unique" in err:
        if "whatsapp_phone_id" in err or "idx_organizations_whatsapp_phone_id_unique" in err:
            raise BusinessLogicError(
                "whatsapp_phone_id já está em uso por outra organização."
            ) from exc
        raise BusinessLogicError("Violação de unicidade nos dados da organização.") from exc
