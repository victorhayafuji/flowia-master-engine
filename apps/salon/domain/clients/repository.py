import logging
from datetime import datetime, timezone

from packages.auth_core.database import db
from packages.auth_core.tenant import get_current_org_id

logger = logging.getLogger(__name__)


class PatientRepository:
    def upsert_handoff_by_sender(self, sender_id: str, reason: str | None = None) -> bool:
        """Persist human handoff on patients (legacy_sender_id = WhatsApp sender)."""
        if not db.client:
            return False

        org_id = get_current_org_id()
        if not org_id or org_id == "ALL":
            logger.warning("Handoff skipped: missing tenant org_id for sender %s", sender_id)
            return False

        try:
            now = datetime.now(timezone.utc).isoformat()
            existing = (
                db.client.table("patients")
                .select("id")
                .eq("organization_id", org_id)
                .eq("legacy_sender_id", sender_id)
                .limit(1)
                .execute()
            )

            payload = {"handoff_requested_at": now, "handoff_reason": reason}

            if existing.data:
                # Scope the write by org too (not just the org-scoped SELECT): the
                # patient already belongs to org_id (ALL short-circuited above), so
                # for a legitimate call this is a no-op, but isolation holds by
                # construction rather than by the SELECT-then-UPDATE sequence.
                db.client.table("patients").update(payload).eq(
                    "id", existing.data[0]["id"]
                ).eq("organization_id", org_id).execute()
            else:
                phone = "".join(filter(str.isdigit, sender_id)) or sender_id
                db.client.table("patients").insert(
                    {
                        "organization_id": org_id,
                        "legacy_sender_id": sender_id,
                        "phone": phone,
                        "name": f"WhatsApp {sender_id[-4:]}",
                        **payload,
                    }
                ).execute()

            logger.info("Handoff recorded for sender %s (org %s)", sender_id, org_id)
            return True
        except Exception as e:
            logger.error("Handoff upsert failed for sender %s: %s", sender_id, e)
            return False
