"""Envia lembretes de agendamento via WhatsApp quando credenciais da org existem."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from packages.auth_core.tenant import set_tenant_context
from packages.integrations.webhook.whatsapp import WhatsAppService
from packages.models.enums import ReminderType
from packages.scheduling.reminder_repository import ReminderRepository

logger = logging.getLogger(__name__)

_PHONE_DIGITS = re.compile(r"\D+")


class ReminderService:
    """Creates appointment reminders and delivers due ones via WhatsApp Cloud API."""

    def __init__(self, repository: ReminderRepository | None = None):
        self.repository = repository or ReminderRepository()

    def create_appointment_reminders(self, appointment: dict[str, Any]) -> list[dict[str, Any]]:
        scheduled_at = _parse_datetime(appointment["scheduled_at"])
        organization_id = appointment["organization_id"]
        appointment_id = appointment["id"]
        patient_id = appointment["patient_id"]

        reminders: list[dict[str, Any]] = []
        specs = [
            (ReminderType.CONFIRMATION_24H, scheduled_at - timedelta(hours=24)),
            (ReminderType.REMINDER_2H, scheduled_at - timedelta(hours=2)),
        ]

        for reminder_type, when in specs:
            if when <= datetime.now(timezone.utc):
                continue
            row = self.repository.create_reminder(
                organization_id=organization_id,
                appointment_id=appointment_id,
                patient_id=patient_id,
                reminder_type=reminder_type,
                scheduled_for=when,
            )
            if row:
                reminders.append(row)

        logger.info(
            "Created %s reminders for appointment %s",
            len(reminders),
            appointment_id,
        )
        return reminders

    def cancel_reminders_for_appointment(self, appointment_id: str | UUID) -> int:
        count = self.repository.cancel_pending_for_appointment(str(appointment_id))
        logger.info("Cancelled %s pending reminders for appointment %s", count, appointment_id)
        return count

    def refresh_reminders_for_appointment(self, appointment: dict[str, Any]) -> list[dict[str, Any]]:
        """Cancel pending reminders and recreate them for the new schedule."""
        self.cancel_reminders_for_appointment(appointment["id"])
        return self.create_appointment_reminders(appointment)

    def process_pending_reminders(self) -> int:
        """Deliver due reminders via WhatsApp; mark_failed when delivery is impossible."""
        now = datetime.now(timezone.utc)
        pending = self.repository.list_pending_due(now)
        processed = 0

        for reminder in pending:
            try:
                self._deliver_reminder(reminder)
                self.repository.mark_sent(reminder["id"])
                processed += 1
            except Exception as exc:
                logger.exception("Failed to process reminder %s", reminder.get("id"))
                self.repository.mark_failed(reminder["id"], str(exc)[:500])

        return processed

    def _deliver_reminder(self, reminder: dict[str, Any]) -> None:
        org_id = str(reminder.get("organization_id") or "")
        if not org_id:
            raise ValueError("organization_id ausente no lembrete")

        phone = self._load_patient_phone(str(reminder["patient_id"]), org_id)
        if not phone:
            raise ValueError("Telefone do cliente não encontrado")

        ctx = self._load_appointment_context(str(reminder["appointment_id"]), org_id)
        message = _build_reminder_message(
            reminder.get("type") or "",
            service_name=ctx.get("service_name") or "seu horário",
            scheduled_label=ctx.get("scheduled_label") or "",
            salon_name=ctx.get("salon_name") or "salão",
        )

        with set_tenant_context(org_id):
            sent = asyncio.run(WhatsAppService().send_text_message(phone, message))

        if not sent:
            raise ValueError("Falha no envio WhatsApp (Graph API)")

        logger.info(
            "Reminder sent org=%s appt=%s type=%s",
            org_id,
            reminder.get("appointment_id"),
            reminder.get("type"),
        )

    def _load_patient_phone(self, patient_id: str, organization_id: str) -> str | None:
        client = self.repository.db.client
        if not client:
            return None
        res = (
            client.table("patients")
            .select("phone")
            .eq("id", patient_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        raw = (res.data[0].get("phone") or "").strip()
        digits = _PHONE_DIGITS.sub("", raw)
        return digits or None

    def _load_appointment_context(self, appointment_id: str, organization_id: str) -> dict[str, str]:
        client = self.repository.db.client
        if not client:
            return {}

        appt_res = (
            client.table("appointments")
            .select("scheduled_at, service_id, organization_id")
            .eq("id", appointment_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not appt_res.data:
            return {}

        row = appt_res.data[0]
        scheduled_at = _parse_datetime(row["scheduled_at"])
        scheduled_label = scheduled_at.strftime("%d/%m às %H:%M")

        service_name = "seu horário"
        service_id = row.get("service_id")
        if service_id:
            svc_res = (
                client.table("service_catalog")
                .select("name")
                .eq("id", service_id)
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )
            if svc_res.data:
                service_name = svc_res.data[0].get("name") or service_name

        org_res = (
            client.table("organizations")
            .select("name")
            .eq("id", organization_id)
            .limit(1)
            .execute()
        )
        salon_name = org_res.data[0].get("name") if org_res.data else "salão"

        return {
            "scheduled_label": scheduled_label,
            "service_name": service_name,
            "salon_name": salon_name,
        }


def _build_reminder_message(
    reminder_type: str,
    *,
    service_name: str,
    scheduled_label: str,
    salon_name: str,
) -> str:
    if reminder_type == ReminderType.CONFIRMATION_24H.value:
        return (
            f"Olá! Aqui é o {salon_name}. "
            f"Lembrete: amanhã você tem {service_name} ({scheduled_label}). "
            "Responda se precisar reagendar."
        )
    if reminder_type == ReminderType.REMINDER_2H.value:
        return (
            f"Olá! Seu {service_name} no {salon_name} é em breve ({scheduled_label}). "
            "Te esperamos!"
        )
    return (
        f"Lembrete do {salon_name}: {service_name} em {scheduled_label}."
    )


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
