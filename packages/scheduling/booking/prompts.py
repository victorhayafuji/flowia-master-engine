"""User-facing booking prompts."""
from __future__ import annotations

from packages.scheduling.date_parsing import format_date_label_pt


def catalog_service_prompt(org_id: str, *, date_iso: str | None = None) -> str:
    from packages.scheduling import booking_executor as be

    catalog = be.list_catalog_services(org_id)
    if not catalog:
        return "Qual serviço você gostaria de agendar?"
    names = ", ".join(row["name"] for row in catalog[:6])
    if date_iso:
        when = format_date_label_pt(date_iso)
        return f"Para {when}, qual serviço você prefere? Temos: {names}."
    return f"Qual serviço deseja agendar? Temos: {names}."
