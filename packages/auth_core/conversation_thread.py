"""Org-scoped LangGraph thread_id helpers."""

from __future__ import annotations

from typing import Any


def build_thread_id(org_id: str, sender_id: str) -> str:
    """Build tenant-isolated thread_id: {organization_id}:{sender_phone_or_session}."""
    return f"{org_id}:{sender_id}"


def thread_id_candidates(org_id: str, sender_id: str) -> list[str]:
    """Primary org-scoped id plus legacy phone-only id (DSAR / retention transition)."""
    primary = build_thread_id(org_id, sender_id)
    if sender_id == primary:
        return [primary]
    return [primary, sender_id]


def patient_thread_id_candidates(org_id: str, patient: dict[str, Any]) -> list[str]:
    """All thread_id variants for a patient record."""
    seen: set[str] = set()
    ordered: list[str] = []
    for sender in (patient.get("legacy_sender_id"), patient.get("phone")):
        if not sender:
            continue
        for tid in thread_id_candidates(org_id, str(sender)):
            if tid not in seen:
                seen.add(tid)
                ordered.append(tid)
    return ordered


def _state_has_values(state_wrapper: Any) -> bool:
    if not state_wrapper or not hasattr(state_wrapper, "values"):
        return False
    values = state_wrapper.values or {}
    return bool(values.get("messages"))


def resolve_read_config(
    org_id: str,
    sender_id: str,
    configurable: dict[str, Any],
    callbacks: list[Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Resolve LangGraph config for reads with legacy fallback.

    Returns (config_for_read, write_config). Writes always use org-scoped thread_id.
    """
    write_thread_id = build_thread_id(org_id, sender_id)
    write_configurable = {**configurable, "thread_id": write_thread_id}
    write_config: dict[str, Any] = {"configurable": write_configurable}
    if callbacks is not None:
        write_config["callbacks"] = callbacks

    read_config = write_config
    return read_config, write_config


def get_state_with_legacy_fallback(
    engine: Any,
    org_id: str,
    sender_id: str,
    configurable: dict[str, Any],
    callbacks: list[Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """
    Load checkpoint state; fallback to legacy phone-only thread_id for reads only.
    """
    read_config, write_config = resolve_read_config(org_id, sender_id, configurable, callbacks)
    state = engine.get_state(read_config)
    if _state_has_values(state):
        return state, write_config

    legacy_configurable = {**configurable, "thread_id": sender_id}
    legacy_config: dict[str, Any] = {"configurable": legacy_configurable}
    if callbacks is not None:
        legacy_config["callbacks"] = callbacks
    legacy_state = engine.get_state(legacy_config)
    if _state_has_values(legacy_state):
        return legacy_state, write_config

    return state, write_config
