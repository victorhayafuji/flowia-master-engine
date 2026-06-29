"""Professional-role scoping (Onda 2 — Frente 4).

A ``role=professional`` user is bound to its own ``professional_id`` (JWT claim).
The ``professional_scope`` dependency surfaces that id, and agenda/overview
endpoints filter their queries to it. This proves an employee can't read another
professional's agenda — within their own org — at the HTTP layer.

Scope note: nav-hiding for Clientes/Catálogo is FRONTEND-only (OrgAdminRoute).
The backend ``/patients`` and ``/organizations/*`` routes are reachable by any
authenticated org member; the protection there is tenant scope, not role. So we
do NOT assert a 403 on those from the backend — that would be testing a
guarantee the backend doesn't make. We assert what the backend DOES enforce:
data scoping by professional_id.
"""
from __future__ import annotations

from tests.conftest import ORG_A, ORG_B, PROFESSIONAL_A


def _empty_appt_chain(mocker):
    chain = mocker.MagicMock()
    for m in ("select", "eq", "gte", "lte", "order", "limit", "neq", "not_", "is_"):
        getattr(chain, m).return_value = chain
    chain.execute.return_value = mocker.MagicMock(data=[], count=0)
    return chain


class TestProfessionalAgendaScope:
    def test_calendar_scoped_to_own_professional(self, client, professional_token, mocker):
        spy = mocker.patch(
            "packages.scheduling.repository.SchedulingRepository.get_appointments_by_date_range",
            return_value=[],
        )
        response = client.get(
            "/api/v1/scheduling/calendar?start_date=2026-06-10&end_date=2026-06-12",
            cookies={"session_token": professional_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        # The repository was constrained to the caller's own professional_id.
        assert spy.call_args.kwargs.get("professional_id") == PROFESSIONAL_A

    def test_dashboard_stats_scoped_to_own_professional(self, client, professional_token, mocker):
        chain = _empty_appt_chain(mocker)
        table = mocker.patch("apps.salon.api.routers.dashboard.db.client.table", return_value=chain)

        response = client.get(
            "/api/v1/dashboard/stats",
            cookies={"session_token": professional_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        # professional path never touches the patients table (prof_scope short-circuits it).
        assert "patients" not in [c.args[0] for c in table.call_args_list]
        # And every appointments query was filtered by the own professional_id.
        eq_calls = [c.args for c in chain.eq.call_args_list]
        assert ("professional_id", PROFESSIONAL_A) in eq_calls

    def test_today_board_scoped_to_own_professional(self, client, professional_token, mocker):
        chain = _empty_appt_chain(mocker)
        mocker.patch("apps.salon.api.routers.dashboard.db.client.table", return_value=chain)

        response = client.get(
            "/api/v1/dashboard/today-board",
            cookies={"session_token": professional_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        eq_calls = [c.args for c in chain.eq.call_args_list]
        # Professionals listing scoped to own id ("id"), appointments to professional_id.
        assert ("id", PROFESSIONAL_A) in eq_calls
        assert ("professional_id", PROFESSIONAL_A) in eq_calls

    def test_agent_summary_professional_gets_zeros_no_query(self, client, professional_token, mocker):
        # A professional gets a zeroed summary and the handler never queries DB
        # (no cross-professional aggregation). Proves no leak by construction.
        table = mocker.patch("apps.salon.api.routers.dashboard.db.client.table")

        response = client.get(
            "/api/v1/dashboard/agent-summary",
            cookies={"session_token": professional_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data == {
            "handoffsPending": 0,
            "appointmentsWhatsappToday": 0,
            "conversationsThisWeek": 0,
        }
        table.assert_not_called()


class TestProfessionalCannotSpoofOrg:
    def test_professional_spoofed_org_returns_403(self, client, professional_token):
        # A professional is still an org-bound role: header≠JWT org → 403.
        response = client.get(
            "/api/v1/scheduling/calendar?start_date=2026-06-10&end_date=2026-06-12",
            cookies={"session_token": professional_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403

    def test_professional_all_header_returns_403(self, client, professional_token):
        response = client.get(
            "/api/v1/scheduling/calendar?start_date=2026-06-10&end_date=2026-06-12",
            cookies={"session_token": professional_token},
            headers={"x-organization-id": "ALL"},
        )
        assert response.status_code == 403
