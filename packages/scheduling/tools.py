import logging
from datetime import datetime
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from packages.auth_core.exceptions import (
    BusinessLogicError,
    DoubleBookingError,
    ResourceNotFoundError,
)
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
from packages.scheduling.patient_booking import find_patient_by_phone, upsert_patient_by_phone
from packages.scheduling.schemas import AppointmentBase
from packages.scheduling.service import SchedulingService
from packages.scheduling.timezone_utils import (
    DEFAULT_TIMEZONE,
    format_local_datetime_label,
    now_local_naive,
    parse_booking_datetime,
    to_local_naive,
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


# ---------------------------------------------------------------------------
# Reagendar / cancelar — agem SOMENTE no agendamento do próprio cliente.
# A identidade vem do canal (telefone do sender no WhatsApp; patient_id do
# seletor no Ensaie), NUNCA de id/telefone fornecido pelo LLM (anti-injeção).
# ---------------------------------------------------------------------------
def _caller_patient_id(config: RunnableConfig) -> str | None:
    cfg = _get_configurable(config)
    sender_phone = cfg.get("sender_phone")
    if sender_phone:
        org_id = cfg.get("org_id")
        patient = find_patient_by_phone(org_id, str(sender_phone)) if org_id else None
        return patient["id"] if patient else None
    pid = cfg.get("patient_id")
    return str(pid) if pid else None


def _format_appt_label(appt: dict, tzname: str) -> str:
    svc = (appt.get("service") or {}).get("name") or "serviço"
    pro = (appt.get("professional") or {}).get("name") or "profissional"
    try:
        dt = datetime.fromisoformat(str(appt["scheduled_at"]).replace("Z", "+00:00"))
        label = format_local_datetime_label(dt, tzname)
    except Exception:
        label = str(appt.get("scheduled_at"))
    return f"{svc} em {label} (com {pro})"


def _filter_appts(
    appts: list[dict], service_name: str | None, original_date: str | None, tzname: str
) -> list[dict]:
    result = appts
    if service_name:
        sn = service_name.strip().lower()
        result = [a for a in result if sn in ((a.get("service") or {}).get("name") or "").lower()]
    if original_date:
        parsed, _ = parse_booking_date(original_date)
        if parsed:
            kept = []
            for a in result:
                try:
                    dt = datetime.fromisoformat(str(a["scheduled_at"]).replace("Z", "+00:00"))
                    if to_local_naive(dt, tzname).date() == parsed:
                        kept.append(a)
                except Exception:
                    continue
            result = kept
    return result


async def _caller_appts(config: RunnableConfig):
    """(org_id, patient_id, [appts futuros], tzname) do dono da conversa."""
    org_id = _get_org_id_from_config(config)
    # set_tenant_context é necessário para _get_org_config() resolver o fuso da org
    # (ele lê get_current_org_id()); sem isso cairia no timezone default.
    with set_tenant_context(org_id):
        sched = SchedulingService()
        tzname = sched._get_org_config()["timezone"]
        patient_id = _caller_patient_id(config)
        if not patient_id:
            return org_id, None, [], tzname
        appts = await sched.get_upcoming_appointments_for_patient(org_id, patient_id)
        return org_id, patient_id, appts, tzname


@tool
async def list_my_appointments(config: RunnableConfig) -> str:
    """Lista os agendamentos FUTUROS do próprio cliente da conversa (para reagendar/cancelar)."""
    try:
        _org, patient_id, appts, tzname = await _caller_appts(config)
        if not patient_id:
            return "Não localizei seu cadastro. Confirme seu nome e telefone para continuar."
        if not appts:
            return "Você não tem agendamentos futuros."
        lines = [f"{i + 1}. {_format_appt_label(a, tzname)}" for i, a in enumerate(appts)]
        return "Seus agendamentos:\n" + "\n".join(lines)
    except Exception as exc:
        logger.error("Erro em list_my_appointments: %s", exc)
        return "Erro ao consultar seus agendamentos."


@tool
async def reschedule_time(
    new_datetime: str,
    config: RunnableConfig,
    service_name: str | None = None,
    original_date: str | None = None,
) -> str:
    """Reagenda o agendamento do próprio cliente para new_datetime (YYYY-MM-DDTHH:MM:00, horário de Brasília).

    Use service_name/original_date para escolher quando o cliente tem mais de um agendamento futuro.
    """
    sender = _sender_key(config)
    ok, _ = check_rate_limit(sender, "book_time")
    if not ok:
        return "Limite de tentativas atingido. Tente novamente mais tarde."
    try:
        org_id, patient_id, appts, tzname = await _caller_appts(config)
        if not patient_id:
            return "Não localizei seu cadastro. Confirme seu nome e telefone para continuar."
        candidates = _filter_appts(appts, service_name, original_date, tzname)
        if not candidates:
            return "Não encontrei um agendamento futuro seu para reagendar."
        if len(candidates) > 1:
            opts = "; ".join(_format_appt_label(a, tzname) for a in candidates)
            return f"Você tem mais de um agendamento. Qual deles? {opts}"

        local_naive, _, dt_err = parse_booking_datetime(new_datetime, tzname, assume_local_wall_clock=True)
        if dt_err or not local_naive:
            return "Horário inválido. Use YYYY-MM-DDTHH:MM:00 em horário de Brasília, sem Z/UTC."

        appt = candidates[0]
        with set_tenant_context(org_id):
            sched = SchedulingService()

            # Não reagendar para o passado.
            if local_naive <= now_local_naive(tzname):
                return "Não consigo reagendar para um horário que já passou. Escolha uma data futura."

            # Valida que o novo horário é um SLOT REAL do profissional (working_hours,
            # break_times, schedule_blocks e buffer) — reschedule_appointment só checa
            # conflito de overlap, então sem isto seria possível cair em folga/3h da manhã.
            prof_id = appt.get("professional_id")
            duration = appt.get("duration_minutes") or 30
            if prof_id:
                available = await sched.get_available_slots(UUID(prof_id), local_naive.date(), duration)
                target_hhmm = local_naive.strftime("%H:%M")
                if not any(
                    datetime.fromisoformat(s).strftime("%H:%M") == target_hhmm for s in available
                ):
                    return (
                        "Esse horário não está disponível para reagendamento. "
                        "Use check_availability para ver os horários livres."
                    )

            try:
                updated = await sched.reschedule_appointment(
                    appointment_id=UUID(appt["id"]),
                    new_scheduled_at=local_naive,
                    organization_id=org_id,
                )
            except DoubleBookingError:
                return "Esse horário já está ocupado. Use check_availability para ver horários livres."
            except (ResourceNotFoundError, BusinessLogicError):
                return "Não consegui reagendar. Verifique os dados e tente novamente."
        label = format_local_datetime_label(
            datetime.fromisoformat(str(updated["scheduled_at"]).replace("Z", "+00:00")), tzname
        )
        return f"SUCESSO! Seu agendamento foi remarcado para {label}."
    except Exception as exc:
        logger.error("Erro em reschedule_time: %s", exc)
        return "Erro ao reagendar. Tente novamente."


@tool
async def cancel_appointment(
    config: RunnableConfig,
    service_name: str | None = None,
    original_date: str | None = None,
    confirm: bool = False,
) -> str:
    """Cancela o agendamento do próprio cliente. SEMPRE confirme com o cliente antes (confirm=true só após o 'sim')."""
    try:
        org_id, patient_id, appts, tzname = await _caller_appts(config)
        if not patient_id:
            return "Não localizei seu cadastro. Confirme seu nome e telefone para continuar."
        candidates = _filter_appts(appts, service_name, original_date, tzname)
        if not candidates:
            return "Não encontrei um agendamento futuro seu para cancelar."
        if len(candidates) > 1:
            opts = "; ".join(_format_appt_label(a, tzname) for a in candidates)
            return f"Você tem mais de um agendamento. Qual deles deseja cancelar? {opts}"

        label = _format_appt_label(candidates[0], tzname)
        if not confirm:
            return f"Confirma o cancelamento de: {label}? Responda 'sim' para confirmar."

        with set_tenant_context(org_id):
            sched = SchedulingService()
            try:
                await sched.update_appointment_status(
                    appointment_id=UUID(candidates[0]["id"]),
                    new_status=AppointmentStatus.CANCELLED,
                    organization_id=org_id,
                )
            except (ResourceNotFoundError, BusinessLogicError):
                return "Não consegui cancelar. Tente novamente."
        return f"Pronto, cancelei: {label}."
    except Exception as exc:
        logger.error("Erro em cancel_appointment: %s", exc)
        return "Erro ao cancelar. Tente novamente."
