"""Tests for multi-tenant isolation via validated_tenant_context."""
from tests.conftest import ORG_A, ORG_B


class TestTenantIsolation:
    def test_org_admin_matching_org_allowed(self, client, user_token, mocker):
        mocker.patch(
            "packages.scheduling.repository.SchedulingRepository.get_appointments_by_date_range",
            return_value=[],
        )
        response = client.get(
            "/api/v1/scheduling/calendar",
            params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200

    def test_org_admin_spoofed_org_returns_403(self, client, user_token):
        response = client.get(
            "/api/v1/scheduling/calendar",
            params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403

    def test_org_admin_all_header_returns_403(self, client, user_token):
        response = client.get(
            "/api/v1/scheduling/calendar",
            params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": "ALL"},
        )
        assert response.status_code == 403

    def test_super_admin_all_header_allowed(self, client, admin_token, mocker):
        mocker.patch(
            "packages.scheduling.repository.SchedulingRepository.get_appointments_by_date_range",
            return_value=[],
        )
        response = client.get(
            "/api/v1/scheduling/calendar",
            params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
            cookies={"session_token": admin_token},
            headers={"x-organization-id": "ALL"},
        )
        assert response.status_code == 200

    def test_super_admin_any_org_allowed(self, client, admin_token, mocker):
        mocker.patch(
            "packages.scheduling.repository.SchedulingRepository.get_appointments_by_date_range",
            return_value=[],
        )
        response = client.get(
            "/api/v1/scheduling/calendar",
            params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
            cookies={"session_token": admin_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 200

    def test_invalid_org_header_returns_400(self, client, user_token):
        response = client.get(
            "/api/v1/scheduling/calendar",
            params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": "not-a-uuid"},
        )
        assert response.status_code == 400

    def test_missing_auth_returns_401(self, client):
        response = client.get(
            "/api/v1/scheduling/calendar",
            params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 401

    def test_patients_spoof_returns_403(self, client, user_token):
        response = client.get(
            "/api/v1/patients/",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403

    def test_catalog_spoof_returns_403(self, client, user_token):
        response = client.get(
            "/api/v1/organizations/services",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403
