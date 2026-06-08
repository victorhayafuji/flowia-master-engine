"""Service ↔ professional eligibility for scheduling tools and API."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from packages.auth_core.database import db
from packages.auth_core.exceptions import BusinessLogicError

ProfessionalRef = dict[str, str]


def list_eligible_professionals(
    org_id: str,
    service_id: str,
    legacy_professional_id: str | None = None,
) -> list[ProfessionalRef]:
    """Returns active professionals eligible for a service, sorted by name.

    Priority: M:N ``service_professionals`` → legacy FK on service → all active pros in org.
    """
    if not db.client:
        return []

    mn = (
        db.client.table("service_professionals")
        .select("professional_id, professional:professionals(id, name, is_active)")
        .eq("service_id", service_id)
        .eq("organization_id", org_id)
        .execute()
    )
    if mn.data:
        pros: list[ProfessionalRef] = []
        for row in mn.data:
            prof = row.get("professional") or {}
            if prof.get("is_active") is False:
                continue
            pid = row.get("professional_id") or prof.get("id")
            if not pid:
                continue
            pros.append({"id": str(pid), "name": prof.get("name") or "Profissional"})
        return sorted(pros, key=lambda p: p["name"].lower())

    if legacy_professional_id:
        res = (
            db.client.table("professionals")
            .select("id, name")
            .eq("id", legacy_professional_id)
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if res.data:
            return [{"id": res.data["id"], "name": res.data["name"]}]

    fallback = (
        db.client.table("professionals")
        .select("id, name")
        .eq("organization_id", org_id)
        .eq("is_active", True)
        .execute()
    )
    return sorted(
        [{"id": r["id"], "name": r["name"]} for r in (fallback.data or [])],
        key=lambda p: p["name"].lower(),
    )


def filter_professionals_by_name(
    professionals: list[ProfessionalRef],
    professional_name: str | None,
) -> list[ProfessionalRef]:
    if not professional_name or not professional_name.strip():
        return professionals
    needle = professional_name.strip().lower()
    return [p for p in professionals if needle in p["name"].lower()]


def has_restricted_eligibility(org_id: str, service_id: str | UUID) -> bool:
    if not db.client:
        return False
    res = (
        db.client.table("service_professionals")
        .select("professional_id", count="exact")
        .eq("service_id", str(service_id))
        .eq("organization_id", org_id)
        .limit(1)
        .execute()
    )
    return bool(res.count)


def assert_professional_eligible(
    org_id: str,
    service_id: str | UUID,
    professional_id: str | UUID,
) -> None:
    """Raises BusinessLogicError when M:N restricts pros and the given pro is not allowed."""
    if not db.client:
        return

    service_id_str = str(service_id)
    professional_id_str = str(professional_id)

    mn = (
        db.client.table("service_professionals")
        .select("professional_id")
        .eq("service_id", service_id_str)
        .eq("organization_id", org_id)
        .execute()
    )
    if not mn.data:
        return

    allowed = {row["professional_id"] for row in mn.data}
    if professional_id_str not in allowed:
        raise BusinessLogicError(
            "O profissional selecionado não está elegível para executar este serviço."
        )


# Synonyms map colloquial terms to catalog search terms (ilike).
_SERVICE_SEARCH_SYNONYMS: dict[str, str] = {
    "mechas": "coloração",
    "mecha": "coloração",
    "retoque": "coloração",
    "balayage": "coloração",
    "luzes": "coloração",
    "corte": "corte",
    "manicure": "manicure",
    "hidratação": "hidratação",
    "hidratacao": "hidratação",
}


def list_catalog_services(org_id: str) -> list[dict[str, Any]]:
    """Active services for the tenant (name, duration, price)."""
    if not db.client:
        return []
    res = (
        db.client.table("service_catalog")
        .select("id, name, duration_minutes, price, professional_id")
        .eq("organization_id", org_id)
        .eq("is_active", True)
        .order("name")
        .execute()
    )
    return res.data or []


def find_service_by_name(org_id: str, service_name: str) -> dict[str, Any] | None:
    from packages.scheduling.guardrails import resolve_service_from_catalog

    service, _err = resolve_service_from_catalog(org_id, service_name)
    return service
