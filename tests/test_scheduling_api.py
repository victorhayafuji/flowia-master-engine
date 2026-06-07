from datetime import datetime, timedelta, timezone
from uuid import uuid4

from packages.auth_core.auth_service import create_access_token
from packages.auth_core.exceptions import DoubleBookingError
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
