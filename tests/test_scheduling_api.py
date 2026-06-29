from datetime import datetime, timedelta, timezone
from uuid import uuid4

from packages.auth_core.auth_service import create_access_token
from packages.auth_core.exceptions import (
    BusinessLogicError,
    DoubleBookingError,
    ResourceNotFoundError,
)
from tests.conftest import ORG_A, ORG_B


class TestSchedulingAPI:
    def test_create_appointment_success(self, client, user_token, mocker):
        payload = {
            "patient_id": str(uuid4()),
            "professional_id": str(uuid4()),
            "service_id": str(uuid4()),
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "duration_minutes": 30,
        }
        mocker.patch(
            "packages.scheduling.service.SchedulingService.create_appointment",
            return_value={"id": str(uuid4()), **payload, "organization_id": ORG_A},
        )

        response = client.post(
            "/api/v1/scheduling/",
            json=payload,
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_create_appointment_double_booking_returns_409(self, client, user_token, mocker):
        payload = {
            "patient_id": str(uuid4()),
            "professional_id": str(uuid4()),
            "service_id": str(uuid4()),
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "duration_minutes": 30,
        }
        mocker.patch(
            "packages.scheduling.service.SchedulingService.create_appointment",
            side_effect=DoubleBookingError("conflito"),
        )

        response = client.post(
            "/api/v1/scheduling/",
            json=payload,
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 409

    def test_tenant_spoof_returns_403(self, client, user_token):
        response = client.post(
            "/api/v1/scheduling/",
            json={
                "patient_id": str(uuid4()),
                "professional_id": str(uuid4()),
                "service_id": str(uuid4()),
                "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "duration_minutes": 30,
            },
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403

    def test_professional_calendar_is_scoped(self, client, mocker):
        prof_id = str(uuid4())
        token = create_access_token(
            data={"sub": "pro@salao.com"},
            role="professional",
            org_id=ORG_A,
            professional_id=prof_id,
        )
        spy = mocker.patch(
            "packages.scheduling.repository.SchedulingRepository.get_appointments_by_date_range",
            return_value=[],
        )

        response = client.get(
            "/api/v1/scheduling/calendar?start_date=2026-06-10&end_date=2026-06-12",
            cookies={"session_token": token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert spy.call_args.kwargs.get("professional_id") == prof_id

    def test_org_admin_calendar_not_scoped(self, client, user_token, mocker):
        spy = mocker.patch(
            "packages.scheduling.repository.SchedulingRepository.get_appointments_by_date_range",
            return_value=[],
        )
        response = client.get(
            "/api/v1/scheduling/calendar?start_date=2026-06-10&end_date=2026-06-12",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert spy.call_args.kwargs.get("professional_id") is None


class TestRescheduleAPI:
    """HTTP-level coverage for POST /scheduling/calendar/{id} (reschedule).

    Scope: router wiring + central exception handlers (app_factory) → HTTP status.
    The reschedule_appointment service method is mocked per scenario, so these
    tests assert the HTTP contract, NOT the internal guard logic — that is owned
    by the service-level/tool tests (test_reschedule_cancel_tools.py and the
    appointments service). Dates are aware UTC + relative (never hardcoded;
    CI runs UTC).
    """

    def _appt_id(self):
        return str(uuid4())

    def test_reschedule_scheduled_at_success(self, client, user_token, mocker):
        appt_id = self._appt_id()
        new_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        spy = mocker.patch(
            "packages.scheduling.service.SchedulingService.reschedule_appointment",
            return_value={"id": appt_id, "scheduled_at": new_at, "organization_id": ORG_A},
        )

        response = client.post(
            f"/api/v1/scheduling/calendar/{appt_id}",
            json={"scheduled_at": new_at},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        # org_id is forwarded to the service (tenant isolation on the write path).
        assert spy.call_args.kwargs.get("organization_id") == ORG_A

    def test_reschedule_duration_only_success(self, client, user_token, mocker):
        # CLAUDE.md §13: scheduled_at and/or duration_minutes (at least one).
        appt_id = self._appt_id()
        mocker.patch(
            "packages.scheduling.service.SchedulingService.reschedule_appointment",
            return_value={"id": appt_id, "duration_minutes": 60, "organization_id": ORG_A},
        )

        response = client.post(
            f"/api/v1/scheduling/calendar/{appt_id}",
            json={"duration_minutes": 60},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_reschedule_empty_body_rejected_422(self, client, user_token):
        # AppointmentUpdate.require_at_least_one_field → pydantic 422 (no service call).
        appt_id = self._appt_id()
        response = client.post(
            f"/api/v1/scheduling/calendar/{appt_id}",
            json={},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 422

    def test_reschedule_conflict_returns_409(self, client, user_token, mocker):
        appt_id = self._appt_id()
        new_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        mocker.patch(
            "packages.scheduling.service.SchedulingService.reschedule_appointment",
            side_effect=DoubleBookingError("conflito"),
        )

        response = client.post(
            f"/api/v1/scheduling/calendar/{appt_id}",
            json={"scheduled_at": new_at},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 409

    def test_reschedule_past_date_returns_422(self, client, user_token, mocker):
        # The past-date guard lives in reschedule_appointment and raises
        # BusinessLogicError → 422 via the central handler.
        appt_id = self._appt_id()
        past_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        mocker.patch(
            "packages.scheduling.service.SchedulingService.reschedule_appointment",
            side_effect=BusinessLogicError(
                "Não é possível reagendar para um horário no passado."
            ),
        )

        response = client.post(
            f"/api/v1/scheduling/calendar/{appt_id}",
            json={"scheduled_at": past_at},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 422

    def test_reschedule_not_found_returns_404(self, client, user_token, mocker):
        appt_id = self._appt_id()
        new_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        mocker.patch(
            "packages.scheduling.service.SchedulingService.reschedule_appointment",
            side_effect=ResourceNotFoundError("não encontrado"),
        )

        response = client.post(
            f"/api/v1/scheduling/calendar/{appt_id}",
            json={"scheduled_at": new_at},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 404

    def test_reschedule_tenant_spoof_returns_403(self, client, user_token, mocker):
        # org_admin header must match JWT org → 403 before reaching the service.
        appt_id = self._appt_id()
        new_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        spy = mocker.patch(
            "packages.scheduling.service.SchedulingService.reschedule_appointment",
            return_value={"id": appt_id},
        )

        response = client.post(
            f"/api/v1/scheduling/calendar/{appt_id}",
            json={"scheduled_at": new_at},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403
        spy.assert_not_called()
