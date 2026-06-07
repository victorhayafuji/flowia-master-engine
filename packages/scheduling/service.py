import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from packages.auth_core.database import db
from packages.auth_core.exceptions import BusinessLogicError, DoubleBookingError
from packages.models.enums import AppointmentStatus
from packages.scheduling.schemas import AppointmentBase

logger = logging.getLogger(__name__)

class SchedulingService:
    def __init__(self):
        self.db = db
        # Mock configurability for working hours
        self.working_hours_start = 9
        self.working_hours_end = 18

    async def get_available_slots(self, professional_id: UUID, target_date: date, service_duration: int) -> list[str]:
        """
        Calcula horários disponíveis (slots) para um profissional em um dia específico.
        Retorna uma lista de strings ISO formatadas.
        """
        start_of_day = datetime.combine(target_date, datetime.min.time()).isoformat()
        end_of_day = datetime.combine(target_date, datetime.max.time()).isoformat()

        # Buscar agendamentos existentes no banco de dados (o context manager já injetará o tenant)
        response = self.db.client.table("appointments").select("scheduled_at, duration_minutes, status") \
            .eq("professional_id", str(professional_id)) \
            .gte("scheduled_at", start_of_day) \
            .lte("scheduled_at", end_of_day) \
            .neq("status", AppointmentStatus.CANCELLED.value) \
            .execute()

        existing_appointments = response.data

        available_slots = []

        # Iniciar no horário de trabalho
        current_time = datetime.combine(target_date, datetime.strptime(f"{self.working_hours_start}:00", "%H:%M").time())
        end_time = datetime.combine(target_date, datetime.strptime(f"{self.working_hours_end}:00", "%H:%M").time())

        # Gerar slots de 30 em 30 minutos (buffer genérico)
        while current_time + timedelta(minutes=service_duration) <= end_time:
            slot_end_time = current_time + timedelta(minutes=service_duration)
            is_conflict = False

            for appt in existing_appointments:
                # Tratar timezone se necessário (Z = UTC). Por enquanto assumimos local/naive.
                raw_scheduled_at = appt["scheduled_at"].replace('Z', '')
                appt_start = datetime.fromisoformat(raw_scheduled_at)
                appt_end = appt_start + timedelta(minutes=appt["duration_minutes"])

                # Check Overlap: StartA < EndB and EndA > StartB
                if (current_time < appt_end) and (slot_end_time > appt_start):
                    is_conflict = True
                    break

            if not is_conflict:
                available_slots.append(current_time.isoformat())

            current_time += timedelta(minutes=30)

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
        new_scheduled_at: datetime,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        """Reagenda mantendo duração e profissional; valida conflitos."""
        query = self.db.client.table("appointments").select("*").eq("id", str(appointment_id))
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        existing = query.maybe_single().execute()
        if not existing.data:
            from packages.auth_core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError(f"Agendamento {appointment_id} não encontrado.")

        row = existing.data
        appointment = AppointmentBase(
            patient_id=row["patient_id"],
            professional_id=row["professional_id"],
            service_id=row["service_id"],
            scheduled_at=new_scheduled_at,
            duration_minutes=row["duration_minutes"],
            status=AppointmentStatus(row.get("status", "confirmed")),
        )

        start_of_day = datetime.combine(new_scheduled_at.date(), datetime.min.time()).isoformat()
        end_of_day = datetime.combine(new_scheduled_at.date(), datetime.max.time()).isoformat()
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
            new_scheduled_at.astimezone(timezone.utc).replace(tzinfo=None)
            if new_scheduled_at.tzinfo
            else new_scheduled_at
        )
        end_time_utc = appt_time_utc + timedelta(minutes=appointment.duration_minutes)

        for c in conflicts.data or []:
            existing_start = datetime.fromisoformat(
                c["scheduled_at"].replace("Z", "+00:00")
            ).astimezone(timezone.utc).replace(tzinfo=None)
            existing_end = existing_start + timedelta(minutes=c["duration_minutes"])
            if (appt_time_utc < existing_end) and (end_time_utc > existing_start):
                raise DoubleBookingError("O profissional já tem um agendamento conflitante neste horário.")

        result = (
            self.db.client.table("appointments")
            .update({"scheduled_at": new_scheduled_at.isoformat()})
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
