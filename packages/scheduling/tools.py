import logging
from datetime import datetime

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from packages.auth_core.database import db
from packages.auth_core.tenant import set_tenant_context
from packages.models.enums import AppointmentStatus
from packages.scheduling.schemas import AppointmentBase
from packages.scheduling.service import SchedulingService

logger = logging.getLogger(__name__)

def _get_org_id_from_config(config: RunnableConfig) -> str:
    """Helper para extrair o org_id blindado do config"""
    org_id = config.get("configurable", {}).get("org_id")
    if not org_id:
        raise ValueError("ERRO CRÍTICO: org_id não injetado no RunnableConfig.")
    return org_id


def _resolve_professional_id(org_id: str, service_data: dict) -> str | None:
    """Resolve o profissional para um serviço.

    Ordem: FK legada (professional_id) -> elegibilidade M:N (service_professionals)
    -> primeiro profissional ativo do salão.
    """
    prof_id = service_data.get("professional_id")
    if prof_id:
        return prof_id

    service_id = service_data.get("id")
    if service_id:
        eligible = (
            db.client.table("service_professionals")
            .select("professional_id")
            .eq("service_id", service_id)
            .eq("organization_id", org_id)
            .execute()
        )
        if eligible.data:
            return eligible.data[0]["professional_id"]

    fallback = (
        db.client.table("professionals")
        .select("id")
        .eq("organization_id", org_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if fallback.data:
        return fallback.data[0]["id"]
    return None

@tool
async def check_availability(service_name: str, target_date: str, config: RunnableConfig) -> str:
    """Busca os horários disponíveis para um serviço específico em uma data específica.
    target_date: Deve ser no formato YYYY-MM-DD.
    """
    logger.info(f"📅 [TOOL] check_availability: {service_name} em {target_date}")

    try:
        org_id = _get_org_id_from_config(config)

        with set_tenant_context(org_id):
            # Busca o serviço para achar o professional_id e a duração
            # LIKE case-insensitive para o service_name
            res = db.client.table("service_catalog").select("id, professional_id, duration_minutes, name") \
                .eq("organization_id", org_id) \
                .ilike("name", f"%{service_name}%") \
                .execute()

            if not res.data:
                return f"Não encontrei nenhum serviço chamado '{service_name}'. Por favor, verifique o nome do serviço."

            service_data = res.data[0]
            professional_id = _resolve_professional_id(org_id, service_data)
            if not professional_id:
                return f"Não há profissional disponível para o serviço '{service_name}'. Cadastre um profissional no catálogo."
            duration_minutes = service_data["duration_minutes"]
            exact_service_name = service_data["name"]

            target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()

            sched_service = SchedulingService()
            available_slots = await sched_service.get_available_slots(
                professional_id=professional_id,
                target_date=target_date_obj,
                service_duration=duration_minutes
            )

            if not available_slots:
                return f"Não há horários disponíveis para '{exact_service_name}' no dia {target_date}."

            formatted_slots = [datetime.fromisoformat(slot).strftime("%H:%M") for slot in available_slots]
            return f"Horários disponíveis para '{exact_service_name}' no dia {target_date}:\n" + ", ".join(formatted_slots)

    except Exception as e:
        logger.error(f"Erro em check_availability: {e}")
        return f"Erro ao verificar disponibilidade: {str(e)}"

@tool
async def book_time(service_name: str, target_datetime: str, patient_name: str, patient_phone: str, config: RunnableConfig) -> str:
    """Agenda um horário para o cliente.
    target_datetime: Formato YYYY-MM-DDTHH:MM:00 (ex: 2026-06-01T14:30:00).
    patient_phone: Formato numérico, ex: 5511999999999.
    """
    logger.info(f"📝 [TOOL] book_time: {service_name} às {target_datetime} para {patient_name}")

    try:
        org_id = _get_org_id_from_config(config)

        with set_tenant_context(org_id):

            # 1. Verifica/Cria o Paciente
            clean_phone = ''.join(filter(str.isdigit, patient_phone))
            patient_res = db.client.table("patients").select("id").eq("organization_id", org_id).eq("phone", clean_phone).execute()

            if patient_res.data:
                patient_id = patient_res.data[0]["id"]
            else:
                # Cria novo cliente
                new_patient = {
                    "organization_id": org_id,
                    "name": patient_name,
                    "phone": clean_phone
                }
                insert_res = db.client.table("patients").insert(new_patient).execute()
                if not insert_res.data:
                    return "Erro ao cadastrar o cliente."
                patient_id = insert_res.data[0]["id"]

            # 2. Busca o Serviço
            srv_res = db.client.table("service_catalog").select("id, professional_id, duration_minutes, name") \
                .eq("organization_id", org_id) \
                .ilike("name", f"%{service_name}%") \
                .execute()

            if not srv_res.data:
                return f"Serviço '{service_name}' não encontrado."

            service_data = srv_res.data[0]
            professional_id = _resolve_professional_id(org_id, service_data)
            if not professional_id:
                return f"Não há profissional disponível para '{service_name}'."
            service_id = service_data["id"]
            duration_minutes = service_data["duration_minutes"]
            exact_service_name = service_data["name"]

            # 3. Cria Agendamento
            sched_datetime = datetime.fromisoformat(target_datetime)

            appointment = AppointmentBase(
                organization_id=org_id,
                professional_id=professional_id,
                patient_id=patient_id,
                service_id=service_id,
                scheduled_at=sched_datetime,
                duration_minutes=duration_minutes,
                status=AppointmentStatus.CONFIRMED
            )

            sched_service = SchedulingService()
            await sched_service.create_appointment(appointment)

            # Envia evento assíncrono para agendar lembretes/anamnese (se houver event bus) ou o DB Trigger faz isso.

            return f"SUCESSO! O agendamento para '{exact_service_name}' foi confirmado para o cliente {patient_name} no dia e horário {target_datetime}."

    except Exception as e:
        logger.error(f"Erro em book_time: {e}")
        return f"Erro ao realizar agendamento. Pode haver um conflito de horário. Detalhe: {str(e)}"
