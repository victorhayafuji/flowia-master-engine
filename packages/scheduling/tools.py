import logging
from datetime import datetime
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from packages.auth_core.tenant import set_tenant_context
from packages.models.enums import AppointmentStatus
from packages.scheduling.eligibility import (
    list_catalog_services as fetch_catalog_services,
)
from packages.scheduling.eligibility import list_eligible_professionals
from packages.scheduling.guardrails import (
    GENERIC_INVALID_MSG,
    check_rate_limit,
    mask_phone,
    parse_booking_date,
    resolve_booking_phone,
    resolve_service_from_catalog,
    sanitize_text_field,
    validate_professional_name,
)
from packages.scheduling.patient_booking import upsert_patient_by_phone
from packages.scheduling.schemas import AppointmentBase
from packages.scheduling.service import SchedulingService
from packages.scheduling.timezone_utils import (
    DEFAULT_TIMEZONE,
    format_local_datetime_label,
    parse_booking_datetime,
)

logger = logging.getLogger(__name__)


def _get_configurable(config: RunnableConfig) -> dict:
    return config.get("configurable") or {}


def _get_org_id_from_config(config: RunnableConfig) -> str:
    org_id = _get_configurable(config).get("org_id")
    if not org_id:
        raise ValueError("ERRO CRÍTICO: org_id não injetado no RunnableConfig.")
    return org_id


def _sender_key(config: RunnableConfig) -> str:
    cfg = _get_configurable(config)
    return str(cfg.get("thread_id") or cfg.get("sender_phone") or cfg.get("org_id") or "")


def _format_slots_grouped(
    exact_service_name: str,
    target_date: str,
    pro_slots: list[tuple[str, list[str]]],
) -> str:
    lines = [f"Horários para '{exact_service_name}' em {target_date} (Brasília / {DEFAULT_TIMEZONE}):"]
    for name, times in pro_slots:
        if times:
            lines.append(f"- {name}: {', '.join(times)}")
    if len(lines) == 1:
        return f"Não há horários disponíveis para '{exact_service_name}' no dia {target_date}."
    return "\n".join(lines)


async def _resolve_professional_for_datetime(
    org_id: str,
    service_data: dict,
    target_datetime: str,
    professional_name: str | None,
    sched_service: SchedulingService,
    tzname: str | None = None,
) -> str | None:
    eligible = list_eligible_professionals(
        org_id,
        service_data["id"],
        service_data.get("professional_id"),
    )
    professionals, pro_err = validate_professional_name(professional_name, eligible)
    if pro_err or not professionals:
        return None

    zone = tzname or sched_service._get_org_config()["timezone"]
    local_naive, _, dt_err = parse_booking_datetime(
        target_datetime,
        zone,
        assume_local_wall_clock=True,
    )
    if dt_err or not local_naive:
        return None

    target_date = local_naive.date()
    target_hhmm = local_naive.strftime("%H:%M")
    duration = service_data["duration_minutes"]

    for pro in professionals:
        slots = await sched_service.get_available_slots(
            UUID(pro["id"]),
            target_date,
            duration,
        )
        for slot in slots:
            slot_hhmm = datetime.fromisoformat(slot).strftime("%H:%M")
            if slot_hhmm == target_hhmm:
                return pro["id"]
    return None


@tool
def list_catalog_services(config: RunnableConfig) -> str:
    """Lista servicos ativos do catalogo do salao (nome, duracao, preco). Use antes de agendar se o cliente usar termo coloquial."""
    try:
        org_id = _get_org_id_from_config(config)
        with set_tenant_context(org_id):
            rows = fetch_catalog_services(org_id)
            if not rows:
                return "Nenhum servico cadastrado no catalogo."
            lines = [
                f"- {r['name']}: {r['duration_minutes']} min, R$ {r['price']}"
                for r in rows
            ]
            return "SERVICOS DO CATALOGO (use estes nomes em check_availability/book_time):\n" + "\n".join(
                lines
            )
    except Exception as exc:
        logger.error("Erro em list_catalog_services: %s", exc)
        return "Erro ao listar servicos do catalogo."


@tool
async def check_availability(
    service_name: str,
    target_date: str,
    config: RunnableConfig,
    professional_name: str | None = None,
) -> str:
    """Busca horários disponíveis para um serviço em uma data.

    target_date: YYYY-MM-DD ou formatos comuns (ex: 10/06/2026, 10 de junho).
    Opcional: professional_name para filtrar a um profissional específico.
    """
    sender = _sender_key(config)
    ok, rate_err = check_rate_limit(sender, "check_availability")
    if not ok:
        return "Muitas consultas de disponibilidade. Aguarde um momento e tente novamente."

    logger.info(
        "check_availability: service=%s date=%s pro=%s sender=%s",
        service_name[:40],
        target_date,
        (professional_name or "")[:40],
        mask_phone(sender) if sender.isdigit() else sender[:8],
    )

    try:
        org_id = _get_org_id_from_config(config)

        with set_tenant_context(org_id):
            parsed_date, date_err = parse_booking_date(target_date)
            if date_err or not parsed_date:
                logger.warning("check_availability rejected: %s (input=%s)", date_err, target_date[:40])
                return (
                    "Data inválida para agendamento. Use YYYY-MM-DD "
                    "(ex: 2026-06-10) ou informe dia e mês claramente."
                )
            if parsed_date.isoformat() != target_date.strip()[:10]:
                logger.info(
                    "check_availability date coerced: %s -> %s",
                    target_date[:40],
                    parsed_date.isoformat(),
                )

            service_data, svc_err = resolve_service_from_catalog(org_id, service_name)
            if svc_err == "ambiguous":
                return "Encontrei mais de um servico parecido. Use list_catalog_services e escolha o nome exato."
            if svc_err or not service_data:
                return (
                    f"Não encontrei nenhum serviço chamado '{service_name}'. "
                    "Use list_catalog_services para ver os nomes disponíveis."
                )

            eligible = list_eligible_professionals(
                org_id,
                service_data["id"],
                service_data.get("professional_id"),
            )
            professionals, pro_err = validate_professional_name(professional_name, eligible)
            if pro_err == "not_found":
                return (
                    f"Não encontrei o profissional '{professional_name}' elegível "
                    f"para '{service_data['name']}'."
                )
            if pro_err or not professionals:
                return (
                    f"Não há profissional disponível para o serviço '{service_data['name']}'. "
                    "Cadastre um profissional no catálogo."
                )

            duration_minutes = service_data["duration_minutes"]
            exact_service_name = service_data["name"]
            date_iso = parsed_date.isoformat()

            sched_service = SchedulingService()
            pro_slots: list[tuple[str, list[str]]] = []
            for pro in professionals:
                available = await sched_service.get_available_slots(
                    professional_id=UUID(pro["id"]),
                    target_date=parsed_date,
                    service_duration=duration_minutes,
                )
                times = [datetime.fromisoformat(slot).strftime("%H:%M") for slot in available]
                if times:
                    pro_slots.append((pro["name"], times))

            return _format_slots_grouped(exact_service_name, date_iso, pro_slots)

    except Exception as exc:
        logger.error("Erro em check_availability: %s", exc)
        return "Erro ao verificar disponibilidade. Tente novamente."


@tool
async def book_time(
    service_name: str,
    target_datetime: str,
    patient_name: str,
    patient_phone: str,
    config: RunnableConfig,
    professional_name: str | None = None,
) -> str:
    """Agenda um horário para o cliente.

    target_datetime: YYYY-MM-DDTHH:MM:00 em horario LOCAL do salao (ex: 2026-06-10T14:30:00).
    Nao use sufixo Z nem converta para UTC — o backend normaliza pelo fuso da organizacao.
    patient_phone: numérico, ex: 5511999999999.
    professional_name: opcional, se o cliente pediu um profissional específico.
    """
    cfg = _get_configurable(config)
    sender = _sender_key(config)
    ok, rate_err = check_rate_limit(sender, "book_time")
    if not ok:
        return "Limite de tentativas de agendamento atingido. Tente novamente mais tarde."

    phone_resolved, phone_note = resolve_booking_phone(patient_phone, cfg)
    logger.info(
        "book_time: service=%s datetime=%s phone=%s pro=%s override=%s",
        service_name[:40],
        target_datetime,
        mask_phone(phone_resolved or patient_phone),
        (professional_name or "")[:40],
        phone_note == "phone_overridden",
    )

    try:
        org_id = _get_org_id_from_config(config)

        with set_tenant_context(org_id):
            if not phone_resolved:
                return GENERIC_INVALID_MSG

            safe_name, name_err = sanitize_text_field(patient_name, 80)
            if name_err or not safe_name:
                return GENERIC_INVALID_MSG

            sched_service = SchedulingService()
            tzname = sched_service._get_org_config()["timezone"]
            local_naive, _, dt_err = parse_booking_datetime(
                target_datetime,
                tzname,
                assume_local_wall_clock=True,
            )
            if dt_err or not local_naive:
                logger.warning("book_time rejected datetime: %s", dt_err)
                return (
                    "Horário inválido. Use formato YYYY-MM-DDTHH:MM:00 "
                    "em horário de Brasília, sem Z/UTC."
                )

            patient_id = upsert_patient_by_phone(org_id, safe_name, phone_resolved)
            if not patient_id:
                return "Erro ao cadastrar o cliente."

            service_data, svc_err = resolve_service_from_catalog(org_id, service_name)
            if svc_err or not service_data:
                return f"Serviço '{service_name}' não encontrado. Use list_catalog_services."

            professional_id = await _resolve_professional_for_datetime(
                org_id,
                service_data,
                target_datetime,
                professional_name,
                sched_service,
                tzname=tzname,
            )
            if not professional_id:
                return (
                    "Horário não disponível para os profissionais elegíveis. "
                    "Use check_availability para ver opções abertas."
                )

            appointment = AppointmentBase(
                professional_id=UUID(professional_id),
                patient_id=UUID(patient_id),
                service_id=UUID(service_data["id"]),
                scheduled_at=local_naive,
                duration_minutes=service_data["duration_minutes"],
                status=AppointmentStatus.CONFIRMED,
            )

            await sched_service.create_appointment(appointment)

            pro_label = professional_name or "profissional disponível"
            local_label = format_local_datetime_label(local_naive, tzname)
            return (
                f"SUCESSO! O agendamento para '{service_data['name']}' foi confirmado "
                f"para {safe_name} em {local_label} "
                f"({pro_label})."
            )

    except Exception as exc:
        logger.error("Erro em book_time: %s", exc)
        return "Erro ao realizar agendamento. Pode haver um conflito de horário."
