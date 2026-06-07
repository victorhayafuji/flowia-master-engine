import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from packages.auth_core.database import db
from packages.auth_core.exceptions import BusinessLogicError, DoubleBookingError
from packages.auth_core.tenant import get_current_org_id
from packages.models.enums import AppointmentStatus
from packages.scheduling.schemas import AppointmentBase, ScheduleBlockBase

logger = logging.getLogger(__name__)

# Monday=0 ... Sunday=6, matching datetime.weekday()
WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DEFAULT_SLOT_MINUTES = 15
DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_WORKING_HOURS = {
    "mon": {"start": "08:00", "end": "18:00"},
    "tue": {"start": "08:00", "end": "18:00"},
    "wed": {"start": "08:00", "end": "18:00"},
    "thu": {"start": "08:00", "end": "18:00"},
    "fri": {"start": "08:00", "end": "18:00"},
}


def _parse_hhmm(value: str) -> time:
    """Parses an 'HH:MM' string into a time object."""
    hour, minute = value.split(":")[:2]
    return time(int(hour), int(minute))


class SchedulingService:
    def __init__(self):
        self.db = db

    def _get_professional_schedule(self, professional_id: UUID) -> dict[str, Any]:
        """Loads working_hours, break_times and buffer for a professional."""
        res = (
            self.db.client.table("professionals")
            .select("working_hours, break_times, appointment_buffer_minutes")
            .eq("id", str(professional_id))
            .maybe_single()
            .execute()
        )
        row = (res.data if res else None) or {}
        buffer = row.get("appointment_buffer_minutes")
        return {
            "working_hours": row.get("working_hours") or DEFAULT_WORKING_HOURS,
            "break_times": row.get("break_times") or [],
            "buffer": int(buffer) if buffer is not None else 0,
        }

    def _get_org_config(self) -> dict[str, Any]:
        """Reads slot step, minimum notice and timezone from organizations.settings."""
        org_id = get_current_org_id()
        slot_step = DEFAULT_SLOT_MINUTES
        min_notice_hours = 0
        tzname = DEFAULT_TIMEZONE
        if org_id and org_id != "ALL":
            try:
                res = (
                    self.db.client.table("organizations")
                    .select("settings, timezone")
                    .eq("id", org_id)
                    .maybe_single()
                    .execute()
                )
                row = (res.data if res else None) or {}
                tzname = row.get("timezone") or DEFAULT_TIMEZONE
                scheduling = (row.get("settings") or {}).get("scheduling") or {}
                slot_step = int(scheduling.get("default_slot_minutes") or DEFAULT_SLOT_MINUTES)
                min_notice_hours = int(scheduling.get("min_notice_hours") or 0)
            except Exception as exc:
                logger.warning("Falling back to default scheduling config: %s", exc)
        return {"slot_step": slot_step, "min_notice_hours": min_notice_hours, "timezone": tzname}

    def _get_day_appointments(self, professional_id: UUID, target_date: date) -> list[dict[str, Any]]:
        """Active appointments for a professional on a given day (excludes cancelled/no_show)."""
        start_of_day = datetime.combine(target_date, datetime.min.time()).isoformat()
        end_of_day = datetime.combine(target_date, datetime.max.time()).isoformat()
        response = (
            self.db.client.table("appointments")
            .select("scheduled_at, duration_minutes, status")
            .eq("professional_id", str(professional_id))
            .gte("scheduled_at", start_of_day)
            .lte("scheduled_at", end_of_day)
            .neq("status", AppointmentStatus.CANCELLED.value)
            .neq("status", AppointmentStatus.NO_SHOW.value)
            .execute()
        )
        return response.data or []

    def _get_day_blocks(self, professional_id: UUID, target_date: date) -> list[dict[str, Any]]:
        """Manual blocks/time off overlapping the day (org-wide when professional_id is null)."""
        start_of_day = datetime.combine(target_date, datetime.min.time()).isoformat()
        end_of_day = datetime.combine(target_date, datetime.max.time()).isoformat()
        org_id = get_current_org_id()
        try:
            query = (
                self.db.client.table("schedule_blocks")
                .select("professional_id, starts_at, ends_at")
                .lte("starts_at", end_of_day)
                .gte("ends_at", start_of_day)
            )
            if org_id and org_id != "ALL":
                query = query.eq("organization_id", org_id)
            response = query.execute()
        except Exception as exc:
            # Table may not exist yet in older deployments — fail open.
            logger.debug("schedule_blocks lookup skipped: %s", exc)
            return []
        rows = response.data or []
        return [
            r for r in rows
            if r.get("professional_id") in (None, str(professional_id))
        ]

    @staticmethod
    def _to_local_naive(raw: str, tzname: str) -> datetime:
        """Converts a stored timestamp into a naive datetime in the org timezone."""
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            try:
                dt = dt.astimezone(ZoneInfo(tzname))
            except Exception:
                pass
            dt = dt.replace(tzinfo=None)
        return dt

    async def get_available_slots(self, professional_id: UUID, target_date: date, service_duration: int) -> list[str]:
        """
        Calcula horários disponíveis para um profissional num dia, respeitando:
        - working_hours do profissional (por dia da semana)
        - break_times (almoço/pausas)
        - bloqueios manuais (schedule_blocks) e folgas
        - buffer entre atendimentos (appointment_buffer_minutes)
        - passo de slot e antecedência mínima (organizations.settings)
        Retorna lista de strings ISO (horário local do salão).
        """
        schedule = self._get_professional_schedule(professional_id)
        org_config = self._get_org_config()

        weekday_key = WEEKDAY_KEYS[target_date.weekday()]
        day_hours = (schedule["working_hours"] or {}).get(weekday_key)
        if not day_hours:
            # Profissional não trabalha neste dia.
            return []

        work_start = datetime.combine(target_date, _parse_hhmm(day_hours["start"]))
        work_end = datetime.combine(target_date, _parse_hhmm(day_hours["end"]))
        buffer = schedule["buffer"]
        slot_step = org_config["slot_step"]
        tzname = org_config["timezone"]

        # Intervalos bloqueados: pausas (parede rígida) + agendamentos e bloqueios (com buffer).
        blocked: list[tuple[datetime, datetime]] = []
        for pause in schedule["break_times"]:
            try:
                blocked.append((
                    datetime.combine(target_date, _parse_hhmm(pause["start"])),
                    datetime.combine(target_date, _parse_hhmm(pause["end"])),
                ))
            except (KeyError, ValueError):
                continue

        for appt in self._get_day_appointments(professional_id, target_date):
            appt_start = self._to_local_naive(appt["scheduled_at"], tzname)
            appt_end = appt_start + timedelta(minutes=appt["duration_minutes"])
            blocked.append((appt_start - timedelta(minutes=buffer), appt_end + timedelta(minutes=buffer)))

        for block in self._get_day_blocks(professional_id, target_date):
            blocked.append((
                self._to_local_naive(block["starts_at"], tzname),
                self._to_local_naive(block["ends_at"], tzname),
            ))

        # Antecedência mínima: descarta slots cedo demais para hoje.
        try:
            now_local = datetime.now(ZoneInfo(tzname)).replace(tzinfo=None)
        except Exception:
            now_local = datetime.now()
        earliest = now_local + timedelta(hours=org_config["min_notice_hours"])

        available_slots: list[str] = []
        current = work_start
        while current + timedelta(minutes=service_duration) <= work_end:
            slot_end = current + timedelta(minutes=service_duration)
            if current >= earliest and not any(
                current < b_end and slot_end > b_start for b_start, b_end in blocked
            ):
                available_slots.append(current.isoformat())
            current += timedelta(minutes=slot_step)

        return available_slots

    async def create_appointment(self, appointment: AppointmentBase) -> dict[str, Any]:
        """
        Cria um agendamento garantindo que não exista conflito de horário.
        """
        # Variável temporária naive para comparações locais
        appt_time_naive = appointment.scheduled_at
        if appt_time_naive.tzinfo is not None:
            appt_time_naive = appt_time_naive.astimezone().replace(tzinfo=None)

        if appt_time_naive < datetime.now():
            raise BusinessLogicError("Não é possível criar agendamentos no passado.")

        start_of_day = datetime.combine(appointment.scheduled_at.date(), datetime.min.time()).isoformat()
        end_of_day = datetime.combine(appointment.scheduled_at.date(), datetime.max.time()).isoformat()

        conflict_query = self.db.client.table("appointments").select("scheduled_at, duration_minutes") \
            .eq("professional_id", str(appointment.professional_id)) \
            .gte("scheduled_at", start_of_day) \
            .lte("scheduled_at", end_of_day) \
            .neq("status", AppointmentStatus.CANCELLED.value)

        conflicts = conflict_query.execute()

        # appointment.scheduled_at is already in UTC or aware. Convert it to UTC naive for comparison
        appt_time_utc = appointment.scheduled_at.astimezone(timezone.utc).replace(tzinfo=None) if appointment.scheduled_at.tzinfo else appointment.scheduled_at
        end_time_utc = appt_time_utc + timedelta(minutes=appointment.duration_minutes)

        for c in conflicts.data:
            existing_start = datetime.fromisoformat(c['scheduled_at'].replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)
            existing_end = existing_start + timedelta(minutes=c['duration_minutes'])

            # Check overlap
            if (appt_time_utc < existing_end) and (end_time_utc > existing_start):
                raise DoubleBookingError("O profissional já tem um agendamento conflitante neste horário.")

        # Inserir no banco
        insert_data = appointment.model_dump(mode='json')
        from packages.auth_core.tenant import get_current_org_id
        current_org_id = get_current_org_id()
        if current_org_id and current_org_id != 'ALL':
            insert_data['organization_id'] = current_org_id

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

        logger.info(f"Agendamento criado com sucesso para o cliente {appointment.patient_id}")
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
        """Reagenda horário e/ou duração; valida conflitos por profissional."""
        query = self.db.client.table("appointments").select("*").eq("id", str(appointment_id))
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        existing = query.maybe_single().execute()
        if not existing.data:
            from packages.auth_core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Agendamento {appointment_id} não encontrado.")

        row = existing.data
        target_scheduled_at = new_scheduled_at or datetime.fromisoformat(
            row["scheduled_at"].replace("Z", "+00:00")
        )
        target_duration = duration_minutes if duration_minutes is not None else row["duration_minutes"]

        appointment = AppointmentBase(
            patient_id=row["patient_id"],
            professional_id=row["professional_id"],
            service_id=row["service_id"],
            scheduled_at=target_scheduled_at,
            duration_minutes=target_duration,
            status=AppointmentStatus(row.get("status", "confirmed")),
        )

        start_of_day = datetime.combine(target_scheduled_at.date(), datetime.min.time()).isoformat()
        end_of_day = datetime.combine(target_scheduled_at.date(), datetime.max.time()).isoformat()
        conflicts = (
            self.db.client.table("appointments")
            .select("id, scheduled_at, duration_minutes")
            .eq("professional_id", str(appointment.professional_id))
            .gte("scheduled_at", start_of_day)
            .lte("scheduled_at", end_of_day)
            .neq("status", AppointmentStatus.CANCELLED.value)
            .neq("id", str(appointment_id))
            .execute()
        )

        appt_time_utc = (
            target_scheduled_at.astimezone(timezone.utc).replace(tzinfo=None)
            if target_scheduled_at.tzinfo
            else target_scheduled_at
        )
        end_time_utc = appt_time_utc + timedelta(minutes=target_duration)

        for c in conflicts.data or []:
            existing_start = datetime.fromisoformat(
                c["scheduled_at"].replace("Z", "+00:00")
            ).astimezone(timezone.utc).replace(tzinfo=None)
            existing_end = existing_start + timedelta(minutes=c["duration_minutes"])
            if (appt_time_utc < existing_end) and (end_time_utc > existing_start):
                raise DoubleBookingError("O profissional já tem um agendamento conflitante neste horário.")

        update_payload: dict[str, Any] = {}
        if new_scheduled_at is not None:
            update_payload["scheduled_at"] = target_scheduled_at.isoformat()
        if duration_minutes is not None:
            update_payload["duration_minutes"] = target_duration

        if not update_payload:
            from packages.auth_core.exceptions import BusinessLogicError
            raise BusinessLogicError("Nada para atualizar.")

        result = (
            self.db.client.table("appointments")
            .update(update_payload)
            .eq("id", str(appointment_id))
            .execute()
        )
        if not result.data:
            from packages.auth_core.exceptions import BusinessLogicError
            raise BusinessLogicError("Erro ao reagendar.")
        return result.data[0]

    async def update_appointment_status(self, appointment_id: UUID, new_status: AppointmentStatus) -> dict[str, Any]:
        """
        Atualiza o status de um agendamento.
        """
        result = self.db.client.table("appointments") \
            .update({"status": new_status.value}) \
            .eq("id", str(appointment_id)) \
            .execute()

        if not result.data:
            from packages.auth_core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Agendamento {appointment_id} não encontrado.")

        logger.info(f"Status do agendamento {appointment_id} atualizado para {new_status.value}")
        updated = result.data[0]

        if new_status == AppointmentStatus.CANCELLED:
            try:
                from packages.scheduling.reminder_service import ReminderService

                ReminderService().cancel_reminders_for_appointment(appointment_id)
            except Exception as exc:
                logger.warning("Failed to cancel reminders for appointment %s: %s", appointment_id, exc)

        return updated

    async def get_agenda(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        """
        Retorna todos os agendamentos de uma organização em um período.
        """
        start_time = datetime.combine(start_date, datetime.min.time()).isoformat()
        end_time = datetime.combine(end_date, datetime.max.time()).isoformat()

        response = self.db.client.table("appointments").select("*, professional:professional_id(*), patient:patient_id(*), service:service_id(*)") \
            .gte("scheduled_at", start_time) \
            .lte("scheduled_at", end_time) \
            .execute()

        return response.data

    async def list_blocks(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        """Lista bloqueios de agenda que tocam o período (folgas, feriados, manuais)."""
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
        """Cria um bloqueio de agenda para um profissional ou para a organização."""
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
        """Remove um bloqueio de agenda."""
        query = self.db.client.table("schedule_blocks").delete().eq("id", str(block_id))
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        result = query.execute()
        if not result.data:
            from packages.auth_core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Bloqueio {block_id} não encontrado.")
        return result.data[0]
