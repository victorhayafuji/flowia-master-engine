"""Patient upsert for AI/booking flows (packages layer — no apps/salon import)."""
from __future__ import annotations

import logging

from packages.auth_core.database import db
from packages.scheduling.guardrails import normalize_phone, sanitize_text_field, validate_phone

logger = logging.getLogger(__name__)

__all__ = [
    "find_patient_by_phone",
    "normalize_phone",
    "upsert_patient_by_phone",
]


def find_patient_by_phone(org_id: str, phone: str) -> dict | None:
    """Return active patient {id, name} matching the org + phone, or None."""
    if not db.client:
        return None
    clean_phone, phone_err = validate_phone(phone)
    if phone_err or not clean_phone:
        return None
    try:
        res = (
            db.client.table("patients")
            .select("id, name")
            .eq("organization_id", org_id)
            .eq("phone", clean_phone)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if res.data:
            return {"id": str(res.data[0]["id"]), "name": res.data[0].get("name") or "Cliente"}
    except Exception as exc:
        logger.warning("find_patient_by_phone failed: %s", exc)
    return None


def upsert_patient_by_phone(org_id: str, name: str, phone: str) -> str | None:
    """Atomic upsert on UNIQUE(organization_id, phone). Returns patient id."""
    if not db.client:
        return None

    clean_phone, phone_err = validate_phone(phone)
    if phone_err or not clean_phone:
        logger.warning("Patient upsert rejected: invalid phone (%s)", phone_err)
        return None

    safe_name, name_err = sanitize_text_field(name, 80)
    if name_err:
        logger.warning("Patient upsert rejected: invalid name (%s)", name_err)
        return None

    payload = {
        "organization_id": org_id,
        "phone": clean_phone,
        "name": safe_name or clean_phone,
        "is_active": True,
    }

    try:
        result = (
            db.client.table("patients")
            .upsert(payload, on_conflict="organization_id,phone")
            .execute()
        )
        if result.data:
            return result.data[0]["id"]
    except Exception as exc:
        logger.warning("Patient upsert failed, falling back to select: %s", exc)
        try:
            existing = (
                db.client.table("patients")
                .select("id")
                .eq("organization_id", org_id)
                .eq("phone", clean_phone)
                .limit(1)
                .execute()
            )
            if existing.data:
                patient_id = existing.data[0]["id"]
                # Scope the fallback write by org too (the SELECT above is already
                # org-scoped, so this is a no-op for a valid call) — keeps tenant
                # isolation by construction, matching the upsert's org constraint.
                update_q = db.client.table("patients").update(
                    {"name": payload["name"], "is_active": True}
                ).eq("id", patient_id)
                if org_id and org_id != "ALL":
                    update_q = update_q.eq("organization_id", org_id)
                update_q.execute()
                return patient_id
        except Exception as fallback_exc:
            logger.warning("Patient upsert fallback also failed: %s", fallback_exc)

    return None
