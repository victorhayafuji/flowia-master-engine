"""Appointment CRUD, agenda listing and schedule blocks."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from packages.auth_core.exceptions import (
    BusinessLogicError,
    DoubleBookingError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from packages.auth_core.tenant import get_current_org_id
from packages.models.enums import AppointmentStatus
from packages.scheduling.schemas import AppointmentBase, ScheduleBlockBase
from packages.scheduling.services.config_helpers import SchedulingConfigMixin
from packages.scheduling.timezone_utils import (
    local_date_range_utc_bounds,
    local_day_utc_bounds,
    normalize_to_utc,
    now_local_naive,
    storage_iso,
    to_local_naive,
)

logger = logging.getLogger(__name__)

# Manual status changes are permissive to allow correcting filling mistakes
# (e.g. undo a wrongly-marked no_show). Any operational status can be set; only
# `pending` (initial) and `rescheduled` (system-managed) are not manual targets.
_MANUAL_TARGET_STATUSES: set[AppointmentStatus] = {
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.ARRIVED,
    AppointmentStatus.IN_PROGRESS,
    AppointmentStatus.COMPLETED,
    AppointmentStatus.NO_SHOW,
    AppointmentStatus.CANCELLED,
}


class SchedulingAppointmentsMixin(SchedulingConfigMixin):
    def _assert_entities_belong_to_org(self, appointment: AppointmentBase, org_id: str) -> None:
        patient = (
            self.db.client.table("patients")
            .select("id")
            .eq("id", str(appointment.patient_id))
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if not patient.data:
            raise BusinessLogicError("Cliente inválido para esta organização.")

        service = (
            self.db.client.table("service_catalog")
            .select("id")
            .eq("id", str(appointment.service_id))
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if not service.data:
            raise BusinessLogicError("Serviço inválido para esta organização.")

        professional = (
            self.db.client.table("professionals")
            .select("id")
            .eq("id", str(appointment.professional_id))
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if not professional.data:
            raise BusinessLogicError("Profissional inválido para esta organização.")

    async def create_appointment(self, appointment: AppointmentBase) -> dict[str, Any]:
        from packages.auth_core.tenant import get_current_org_id
        from packages.scheduling.eligibility import assert_professional_eligible

        current_org_id = get_current_org_id()
        if current_org_id and current_org_id != "ALL":
            assert_professional_eligible(
                current_org_id,
                appointment.service_id,
                appointment.professional_id,
            )
            self._assert_entities_belong_to_org(appointment, current_org_id)

        org_config = self._get_org_config()
        tzname = org_config["timezone"]
        scheduled_utc = normalize_to_utc(appointment.scheduled_at, tzname)
        sched_local = to_local_naive(scheduled_utc, tzname)

        if sched_local < now_local_naive(tzname):
            raise BusinessLogicError("Não é possível criar agendamentos no passado.")

        start_of_day, end_of_day = local_day_utc_bounds(sched_local.date(), tzname)

        conflict_query = (
            self.db.client.table("appointments")
            .select("scheduled_at, duration_minutes")
            .eq("professional_id", str(appointment.professional_id))
            .gte("scheduled_at", start_of_day)
            .lte("scheduled_at", end_of_day)
            .neq("status", AppointmentStatus.CANCELLED.value)
        )

        conflicts = conflict_query.execute()

        appt_time_utc = scheduled_utc.replace(tzinfo=None)
        end_time_utc = appt_time_utc + timedelta(minutes=appointment.duration_minutes)

        for c in conflicts.data:
            existing_start = datetime.fromisoformat(c["scheduled_at"].replace("Z", "+00:00")).astimezone(
                timezone.utc
            ).replace(tzinfo=None)
            existing_end = existing_start + timedelta(minutes=c["duration_minutes"])

            if (appt_time_utc < existing_end) and (end_time_utc > existing_start):
                raise DoubleBookingError("O profissional já tem um agendamento conflitante neste horário.")

        insert_data = appointment.model_dump(mode="json")
        insert_data["scheduled_at"] = storage_iso(scheduled_utc)
        if current_org_id and current_org_id != "ALL":
            insert_data["organization_id"] = current_org_id

        try:
            result = self.db.client.table("appointments").insert(insert_data).execute()
        except Exception as exc:
            err = str(exc).lower()
            if "exclusion" in err or "overlap" in err or "23p01" in err:
                raise DoubleBookingError(
                    "O profissional já tem um agendamento conflitante neste horário."
                ) from exc
            raise

        if not result.data:
            raise BusinessLogicError("Erro ao inserir agendamento no banco de dados.")

        logger.info("Agendamento criado com sucesso para o cliente %s", appointment.patient_id)
        created = result.data[0]

        try:
            from packages.scheduling.reminder_service import ReminderService

            ReminderService().create_appointment_reminders(created)
        except Exception as exc:
            logger.warning("Failed to create reminders for appointment %s: %s", created.get("id"), exc)

        return created

    async def reschedule_appointment(
        self,
        appointment_id: UUID,
        new_scheduled_at: datetime | None = None,
        duration_minutes: int | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        query = self.db.client.table("appointments").select("*").eq("id", str(appointment_id))
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        existing = query.maybe_single().execute()
        if not existing.data:
            raise ResourceNotFoundError(f"Agendamento {appointment_id} não encontrado.")

        row = existing.data
        org_config = self._get_org_config()
        tzname = org_config["timezone"]
        raw_scheduled = new_scheduled_at or datetime.fromisoformat(row["scheduled_at"].replace("Z", "+00:00"))
        target_scheduled_at = normalize_to_utc(raw_scheduled, tzname) if raw_scheduled else None
        if target_scheduled_at is None:
            raise BusinessLogicError("Horário inválido.")
        target_duration = duration_minutes if duration_minutes is not None else row["duration_minutes"]

        sched_local = to_local_naive(target_scheduled_at, tzname)
        start_of_day, end_of_day = local_day_utc_bounds(sched_local.date(), tzname)
        conflicts = (
            self.db.client.table("appointments")
            .select("id, scheduled_at, duration_minutes")
            .eq("professional_id", str(row["professional_id"]))
            .gte("scheduled_at", start_of_day)
            .lte("scheduled_at", end_of_day)
            .neq("status", AppointmentStatus.CANCELLED.value)
            .neq("id", str(appointment_id))
            .execute()
        )

        appt_time_utc = target_scheduled_at.replace(tzinfo=None)
        end_time_utc = appt_time_utc + timedelta(minutes=target_duration)

        for c in conflicts.data or []:
            existing_start = datetime.fromisoformat(c["scheduled_at"].replace("Z", "+00:00")).astimezone(
                timezone.utc
            ).replace(tzinfo=None)
            existing_end = existing_start + timedelta(minutes=c["duration_minutes"])
            if (appt_time_utc < existing_end) and (end_time_utc > existing_start):
                raise DoubleBookingError("O profissional já tem um agendamento conflitante neste horário.")

        update_payload: dict[str, Any] = {}
        if new_scheduled_at is not None:
            update_payload["scheduled_at"] = storage_iso(target_scheduled_at)
        if duration_minutes is not None:
            update_payload["duration_minutes"] = target_duration

        if not update_payload:
            raise BusinessLogicError("Nada para atualizar.")

        result = (
            self.db.client.table("appointments")
            .update(update_payload)
            .eq("id", str(appointment_id))
            .execute()
        )
        if not result.data:
            raise BusinessLogicError("Erro ao reagendar.")
        updated = {**row, **result.data[0]}

        try:
            from packages.scheduling.reminder_service import ReminderService

            ReminderService().refresh_reminders_for_appointment(updated)
        except Exception as exc:
            logger.warning("Failed to refresh reminders for appointment %s: %s", appointment_id, exc)

        return updated

    async def get_upcoming_appointments_for_patient(
        self, organization_id: str | None, patient_id: str
    ) -> list[dict[str, Any]]:
        """Agendamentos futuros e ativos do paciente (para reagendar/cancelar via agente)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        query = (
            self.db.client.table("appointments")
            .select(
                "id, scheduled_at, duration_minutes, status, service_id, professional_id, "
                "service:service_catalog(name), professional:professionals(name)"
            )
            .eq("patient_id", str(patient_id))
            .gte("scheduled_at", now_iso)
            .not_.in_(
                "status",
                [AppointmentStatus.CANCELLED.value, AppointmentStatus.NO_SHOW.value],
            )
            .order("scheduled_at")
        )
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        return query.execute().data or []

    async def update_appointment_status(
        self,
        appointment_id: UUID,
        new_status: AppointmentStatus,
        organization_id: str | None = None,
        professional_id: str | None = None,
    ) -> dict[str, Any]:
        query = self.db.client.table("appointments").select("*").eq("id", str(appointment_id))
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        existing = query.maybe_single().execute()
        if not existing.data:
            raise ResourceNotFoundError(f"Agendamento {appointment_id} não encontrado.")

        row = existing.data

        # Professional scope: a logged-in professional may only change their own appointments.
        if professional_id and str(row.get("professional_id")) != str(professional_id):
            raise PermissionDeniedError("Você só pode alterar agendamentos da sua própria agenda.")

        current = AppointmentStatus(row["status"])
        if new_status == current:
            return row

        if new_status not in _MANUAL_TARGET_STATUSES:
            raise BusinessLogicError(
                f"O status {new_status.value} não pode ser definido manualmente."
            )

        result = (
            self.db.client.table("appointments")
            .update({"status": new_status.value})
            .eq("id", str(appointment_id))
            .execute()
        )

        if not result.data:
            raise ResourceNotFoundError(f"Agendamento {appointment_id} não encontrado.")

        logger.info("Status do agendamento %s atualizado para %s", appointment_id, new_status.value)
        updated = {**row, **result.data[0]}

        # Keep patients.no_show_count consistent: +1 when entering no_show, -1 when a
        # mistaken no_show is corrected to any other status.
        patient_id = row.get("patient_id")
        if patient_id:
            if new_status == AppointmentStatus.NO_SHOW and current != AppointmentStatus.NO_SHOW:
                self._adjust_patient_no_show_count(patient_id, +1)
            elif current == AppointmentStatus.NO_SHOW and new_status != AppointmentStatus.NO_SHOW:
                self._adjust_patient_no_show_count(patient_id, -1)

        if new_status == AppointmentStatus.CANCELLED:
            try:
                from packages.scheduling.reminder_service import ReminderService

                ReminderService().cancel_reminders_for_appointment(appointment_id)
            except Exception as exc:
                logger.warning("Failed to cancel reminders for appointment %s: %s", appointment_id, exc)

        return updated

    def _adjust_patient_no_show_count(self, patient_id: str, delta: int) -> None:
        """Adjust patients.no_show_count by delta (floored at 0) so manual changes stay consistent."""
        current = (
            self.db.client.table("patients")
            .select("no_show_count")
            .eq("id", patient_id)
            .maybe_single()
            .execute()
        )
        count = (current.data or {}).get("no_show_count") or 0
        new_count = max(0, count + delta)
        self.db.client.table("patients").update({"no_show_count": new_count}).eq(
            "id", patient_id
        ).execute()

    async def get_agenda(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        tzname = self._get_org_config()["timezone"]
        start_time, end_time = local_date_range_utc_bounds(start_date, end_date, tzname)

        response = (
            self.db.client.table("appointments")
            .select("*, professional:professional_id(*), patient:patient_id(*), service:service_id(*)")
            .gte("scheduled_at", start_time)
            .lte("scheduled_at", end_time)
            .execute()
        )

        return response.data

    async def list_blocks(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        start_time = datetime.combine(start_date, datetime.min.time()).isoformat()
        end_time = datetime.combine(end_date, datetime.max.time()).isoformat()
        org_id = get_current_org_id()
        query = (
            self.db.client.table("schedule_blocks")
            .select("*, professional:professional_id(id, name)")
            .lte("starts_at", end_time)
            .gte("ends_at", start_time)
        )
        if org_id and org_id != "ALL":
            query = query.eq("organization_id", org_id)
        response = query.execute()
        return response.data or []

    async def create_block(self, block: ScheduleBlockBase) -> dict[str, Any]:
        if block.ends_at <= block.starts_at:
            raise BusinessLogicError("O fim do bloqueio deve ser depois do início.")
        insert_data = block.model_dump(mode="json")
        org_id = get_current_org_id()
        if org_id and org_id != "ALL":
            insert_data["organization_id"] = org_id
        result = self.db.client.table("schedule_blocks").insert(insert_data).execute()
        if not result.data:
            raise BusinessLogicError("Erro ao criar bloqueio de agenda.")
        return result.data[0]

    async def delete_block(self, block_id: UUID, organization_id: str | None = None) -> dict[str, Any]:
        query = self.db.client.table("schedule_blocks").delete().eq("id", str(block_id))
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        result = query.execute()
        if not result.data:
            raise ResourceNotFoundError(f"Bloqueio {block_id} não encontrado.")
        return result.data[0]
