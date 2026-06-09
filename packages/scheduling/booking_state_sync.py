"""Reconcile LangGraph booking slots with thread parsers (state = cache, thread = truth)."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import BaseMessage

from packages.engine.routing import is_booking_confirmed_in_thread
from packages.scheduling.booking_flow_memory import (
    BookingFlowStep,
    build_date_choice_redirect_message,
    is_date_choice_opinion_question,
)
from packages.scheduling.timezone_utils import extract_booking_time_from_text

logger = logging.getLogger(__name__)

PendingClarification = Literal["date", "service", "time", "patient"]
MissingField = Literal["date", "service", "time", "patient_name", "patient_phone"]


@dataclass(frozen=True)
class BookingStateSnapshot:
    """Checkpoint consultável do fluxo de agendamento (stateOfMemory)."""

    booking_date: str | None
    booking_service: str | None
    booking_time: str | None
    booking_patient_name: str | None
    booking_patient_phone: str | None
    booking_step: str | None
    clarification: str | None = None
    pending_clarification: PendingClarification | None = None
    missing_fields: tuple[MissingField, ...] = ()


def has_open_date_clarification(snapshot: BookingStateSnapshot) -> bool:
    return snapshot.pending_clarification == "date"


def date_is_resolved(snapshot: BookingStateSnapshot) -> bool:
    return bool(snapshot.booking_date) and not has_open_date_clarification(snapshot)


def derive_missing_fields(
    *,
    booking_date: str | None,
    booking_service: str | None,
    booking_time: str | None,
    booking_patient_name: str | None,
    booking_patient_phone: str | None,
    step: BookingFlowStep,
) -> tuple[MissingField, ...]:
    missing: list[MissingField] = []
    if not booking_date:
        missing.append("date")
    if not booking_service:
        missing.append("service")
    if booking_date and booking_service and not booking_time:
        if step in {BookingFlowStep.AWAITING_TIME, BookingFlowStep.AWAITING_PATIENT}:
            missing.append("time")
    if booking_date and booking_service and booking_time:
        if not booking_patient_name:
            missing.append("patient_name")
        if not booking_patient_phone:
            missing.append("patient_phone")
    return tuple(missing)


def derive_pending_clarification(
    *,
    clarification: str | None,
    booking_date: str | None,
) -> PendingClarification | None:
    if clarification and not booking_date:
        return "date"
    return None


def get_checkpoint_clarification_message(
    snapshot: BookingStateSnapshot,
    last: str,
) -> str | None:
    """Prompt determinístico a partir do checkpoint — sem re-parse ambíguo do thread."""
    if snapshot.pending_clarification != "date" or not snapshot.clarification:
        return None
    if is_date_choice_opinion_question(last):
        return build_date_choice_redirect_message(snapshot.clarification)
    return snapshot.clarification


def clear_booking_state() -> dict[str, None]:
    """Return dict patch that clears all booking_* LangGraph slots."""
    return {
        "booking_date": None,
        "booking_service": None,
        "booking_time": None,
        "booking_patient_name": None,
        "booking_patient_phone": None,
        "booking_step": None,
        "booking_pending_clarification": None,
        "booking_missing_fields": None,
    }


def derive_booking_step(
    messages: Sequence[BaseMessage],
    *,
    booking_date: str | None,
    booking_service: str | None,
    booking_time: str | None,
    booking_patient_name: str | None,
    booking_patient_phone: str | None,
) -> BookingFlowStep:
    if is_booking_confirmed_in_thread(list(messages)):
        return BookingFlowStep.COMPLETE

    if booking_date and booking_service:
        if booking_time:
            return BookingFlowStep.AWAITING_PATIENT
        from packages.scheduling.booking_flow_memory import _awaiting_patient_data

        if _awaiting_patient_data(messages):
            return BookingFlowStep.AWAITING_PATIENT
        return BookingFlowStep.AWAITING_TIME

    if booking_service and not booking_date:
        return BookingFlowStep.NEED_DATE
    if booking_date and not booking_service:
        return BookingFlowStep.NEED_SERVICE
    return BookingFlowStep.IDLE


def sync_booking_state(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
    booking_time: str | None = None,
    booking_patient_name: str | None = None,
    booking_patient_phone: str | None = None,
) -> BookingStateSnapshot:
    from packages.scheduling.booking_executor import (
        _human_texts,
        _wants_date_reset,
        extract_patient_name,
        extract_patient_phone,
        resolve_booking_context,
    )

    texts = _human_texts(messages)
    last = texts[-1] if texts else ""
    combined = " ".join(texts)
    prior_date = booking_date

    incoming_checkpoint: BookingStateSnapshot | None = None
    if booking_date:
        incoming_checkpoint = BookingStateSnapshot(
            booking_date=booking_date,
            booking_service=booking_service,
            booking_time=booking_time,
            booking_patient_name=booking_patient_name,
            booking_patient_phone=booking_patient_phone,
            booking_step=None,
        )

    merged_date, merged_service, clarification = resolve_booking_context(
        messages,
        org_id,
        booking_date=booking_date,
        booking_service=booking_service,
        checkpoint=incoming_checkpoint,
    )

    if _wants_date_reset(last):
        merged_date = None
        merged_time = None
        clarification = None
    else:
        time_from_last = extract_booking_time_from_text(last) if last else None
        time_from_combined = extract_booking_time_from_text(combined) if combined else None
        merged_time = time_from_last or time_from_combined or booking_time

        if merged_date and prior_date and merged_date != prior_date and not time_from_last:
            merged_time = None
        elif not merged_date:
            merged_time = None

    name_from_thread = extract_patient_name(combined) if combined else None
    phone_from_thread = extract_patient_phone(combined) if combined else None
    merged_name = name_from_thread or booking_patient_name
    merged_phone = phone_from_thread or booking_patient_phone

    step = derive_booking_step(
        messages,
        booking_date=merged_date,
        booking_service=merged_service,
        booking_time=merged_time,
        booking_patient_name=merged_name,
        booking_patient_phone=merged_phone,
    )

    pending = derive_pending_clarification(
        clarification=clarification,
        booking_date=merged_date,
    )
    missing = derive_missing_fields(
        booking_date=merged_date,
        booking_service=merged_service,
        booking_time=merged_time,
        booking_patient_name=merged_name,
        booking_patient_phone=merged_phone,
        step=step,
    )

    logger.info(
        "booking_sync | step=%s pending=%s missing=%s date=%s service=%s time=%s",
        step.value,
        pending,
        missing,
        merged_date,
        merged_service,
        merged_time,
    )

    return BookingStateSnapshot(
        booking_date=merged_date,
        booking_service=merged_service,
        booking_time=merged_time,
        booking_patient_name=merged_name,
        booking_patient_phone=merged_phone,
        booking_step=step.value,
        clarification=clarification,
        pending_clarification=pending,
        missing_fields=missing,
    )


def snapshot_to_state_patch(snapshot: BookingStateSnapshot) -> dict[str, str | None | list[str]]:
    return {
        "booking_date": snapshot.booking_date,
        "booking_service": snapshot.booking_service,
        "booking_time": snapshot.booking_time,
        "booking_patient_name": snapshot.booking_patient_name,
        "booking_patient_phone": snapshot.booking_patient_phone,
        "booking_step": snapshot.booking_step,
        "booking_pending_clarification": snapshot.pending_clarification,
        "booking_missing_fields": list(snapshot.missing_fields) or None,
    }
