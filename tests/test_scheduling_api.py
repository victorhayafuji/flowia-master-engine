from datetime import datetime, timedelta, timezone
from uuid import uuid4

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
