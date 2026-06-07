"""Persist WhatsApp/chat session state (handoff) on patients."""


def update_session_state(sender_id: str, data: dict) -> bool:
    from apps.salon.domain.clients.repository import PatientRepository

    reason = data.get("handoff_reason") or data.get("reason")
    return PatientRepository().upsert_handoff_by_sender(sender_id, reason=reason)
