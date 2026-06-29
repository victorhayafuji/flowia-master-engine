"""LGPD consent gate — first-contact privacy notice (WhatsApp / chat)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from packages.auth_core.config import settings
from packages.auth_core.database import db

logger = logging.getLogger(__name__)

PRIVACY_NOTICE_VERSION = "2026-06"


class ConsentAction(str, Enum):
    SEND_NOTICE = "send_notice"
    RECORD_CONSENT = "record_consent"
    PROCEED = "proceed"


def build_privacy_notice(org_name: str) -> str:
    contact = settings.PRIVACY_CONTACT_EMAIL or "contato@gaussix.com"
    policy_url = settings.PRIVACY_POLICY_URL
    return (
        f"Olá! Sou a assistente virtual do {org_name}.\n\n"
        "Para atendê-lo(a), tratamos dados como nome e telefone para agendamentos e "
        "histórico de conversa via WhatsApp, conforme a LGPD.\n\n"
        f"Saiba mais: {policy_url}\n"
        f"Dúvidas ou direitos (acesso, correção, exclusão): {contact}\n\n"
        "Ao continuar esta conversa, você concorda com esse tratamento."
    )


def has_valid_consent(patient: dict[str, Any] | None) -> bool:
    if not patient:
        return False
    return bool(patient.get("privacy_consent_at"))


def _phone_from_sender(sender_id: str) -> str:
    digits = "".join(c for c in sender_id if c.isdigit())
    return digits or sender_id


def find_patient_by_sender(org_id: str, sender_id: str) -> dict[str, Any] | None:
    if not db.client or not org_id or org_id == "ALL":
        return None
    try:
        by_legacy = (
            db.client.table("patients")
            .select("*")
            .eq("organization_id", org_id)
            .eq("legacy_sender_id", sender_id)
            .limit(1)
            .execute()
        )
        if by_legacy.data:
            return by_legacy.data[0]
        phone = _phone_from_sender(sender_id)
        by_phone = (
            db.client.table("patients")
            .select("*")
            .eq("organization_id", org_id)
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        if by_phone.data:
            return by_phone.data[0]
    except Exception as exc:
        logger.warning("find_patient_by_sender failed: %s", exc)
    return None


def _get_org_name(org_id: str) -> str:
    if not db.client:
        return "salão"
    try:
        row = (
            db.client.table("organizations")
            .select("name")
            .eq("id", org_id)
            .limit(1)
            .execute()
        )
        if row.data:
            return row.data[0].get("name") or "salão"
    except Exception:
        pass
    return "salão"


def record_notice_shown(org_id: str, sender_id: str, channel: str) -> None:
    if not db.client:
        return
    now = datetime.now(timezone.utc).isoformat()
    patient = find_patient_by_sender(org_id, sender_id)
    payload = {
        "privacy_notice_version": PRIVACY_NOTICE_VERSION,
        "privacy_notice_shown_at": now,
        "privacy_consent_channel": channel,
    }
    try:
        if patient:
            # Scope the write by org too (not just the org-scoped lookup) so tenant
            # isolation holds by construction. The patient already belongs to org_id.
            db.client.table("patients").update(payload).eq("id", patient["id"]).eq(
                "organization_id", org_id
            ).execute()
        else:
            phone = _phone_from_sender(sender_id)
            db.client.table("patients").insert(
                {
                    "organization_id": org_id,
                    "legacy_sender_id": sender_id,
                    "phone": phone,
                    "name": f"WhatsApp {sender_id[-4:]}" if len(sender_id) >= 4 else "WhatsApp",
                    "is_active": True,
                    **payload,
                }
            ).execute()
    except Exception as exc:
        logger.error("record_notice_shown failed: %s", exc)


def record_consent(org_id: str, sender_id: str, channel: str) -> None:
    if not db.client:
        return
    now = datetime.now(timezone.utc).isoformat()
    patient = find_patient_by_sender(org_id, sender_id)
    payload = {
        "privacy_consent_at": now,
        "privacy_consent_channel": channel,
        "privacy_notice_version": PRIVACY_NOTICE_VERSION,
        # An explicit consent always clears a prior refusal — gives the gate an exit
        # via "Concordo" after a "Discordo".
        "privacy_declined_at": None,
    }
    try:
        if patient:
            if not patient.get("privacy_notice_shown_at"):
                payload["privacy_notice_shown_at"] = now
            db.client.table("patients").update(payload).eq("id", patient["id"]).eq(
                "organization_id", org_id
            ).execute()
        else:
            phone = _phone_from_sender(sender_id)
            db.client.table("patients").insert(
                {
                    "organization_id": org_id,
                    "legacy_sender_id": sender_id,
                    "phone": phone,
                    "name": f"WhatsApp {sender_id[-4:]}" if len(sender_id) >= 4 else "WhatsApp",
                    "is_active": True,
                    "privacy_notice_shown_at": now,
                    **payload,
                }
            ).execute()
    except Exception as exc:
        logger.error("record_consent failed: %s", exc)


def record_decline(org_id: str, sender_id: str, channel: str) -> None:
    """Persist an explicit consent refusal ("Discordo") without recording consent.

    Honors the data subject's refusal: the next message will re-present the notice
    instead of being treated as tacit consent (see ``evaluate_consent_gate``).
    """
    if not db.client:
        return
    now = datetime.now(timezone.utc).isoformat()
    patient = find_patient_by_sender(org_id, sender_id)
    payload = {
        "privacy_declined_at": now,
        "privacy_consent_channel": channel,
        "privacy_notice_version": PRIVACY_NOTICE_VERSION,
    }
    try:
        if patient:
            db.client.table("patients").update(payload).eq("id", patient["id"]).eq(
                "organization_id", org_id
            ).execute()
        else:
            phone = _phone_from_sender(sender_id)
            db.client.table("patients").insert(
                {
                    "organization_id": org_id,
                    "legacy_sender_id": sender_id,
                    "phone": phone,
                    "name": f"WhatsApp {sender_id[-4:]}" if len(sender_id) >= 4 else "WhatsApp",
                    "is_active": True,
                    **payload,
                }
            ).execute()
    except Exception as exc:
        logger.error("record_decline failed: %s", exc)


def evaluate_consent_gate(org_id: str, sender_id: str, channel: str) -> tuple[ConsentAction, str | None, bool]:
    """
    Returns (action, notice_message, lgpd_shown).
    - SEND_NOTICE: respond with notice only; do not run engine
    - RECORD_CONSENT: consent recorded; proceed with engine
    - PROCEED: already consented
    """
    patient = find_patient_by_sender(org_id, sender_id)
    if has_valid_consent(patient):
        return ConsentAction.PROCEED, None, True

    org_name = _get_org_name(org_id)

    # Honor an explicit refusal: re-present the notice and do NOT consent tacitly.
    # This branch precedes the tácito path, so a persisted "Discordo" is never
    # overridden by the next message. Exit is via an explicit "Concordo"
    # (record_consent clears privacy_declined_at).
    if patient and patient.get("privacy_declined_at") and not patient.get("privacy_consent_at"):
        notice = build_privacy_notice(org_name)
        return ConsentAction.SEND_NOTICE, notice, False

    if patient and patient.get("privacy_notice_shown_at") and not patient.get("privacy_consent_at"):
        record_consent(org_id, sender_id, channel)
        return ConsentAction.RECORD_CONSENT, None, True

    notice = build_privacy_notice(org_name)
    record_notice_shown(org_id, sender_id, channel)
    return ConsentAction.SEND_NOTICE, notice, False
