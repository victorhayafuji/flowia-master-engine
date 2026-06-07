"""Tests for the auth dependency layer: auth_required and admin_required."""

from packages.auth_core.config import settings


class TestAuthRequired:
    """Tests for the auth_required dependency."""

    def test_valid_cookie_accepted(self, client, admin_token):
        response = client.get(
            "/api/v1/metrics/kpis",
            cookies={"session_token": admin_token},
        )
        # Should not be 401 — the endpoint is protected by auth_required
        assert response.status_code != 401

    def test_valid_api_key_accepted(self, client):
        response = client.get(
            "/api/v1/metrics/kpis",
            headers={"X-API-KEY": settings.DASHBOARD_API_KEY},
        )
        assert response.status_code != 401

    def test_no_credentials_returns_401(self, client):
        response = client.get("/api/v1/metrics/kpis")
        assert response.status_code == 401

    def test_invalid_api_key_returns_401(self, client):
        response = client.get(
            "/api/v1/metrics/kpis",
            headers={"X-API-KEY": "wrong-key-12345"},
        )
        assert response.status_code == 401

    def test_expired_token_returns_401(self, client, expired_token):
        response = client.get(
            "/api/v1/metrics/kpis",
            cookies={"session_token": expired_token},
        )
        assert response.status_code == 401


class TestAdminRequired:
    """Tests for the admin_required dependency."""

    def test_super_admin_accepted(self, client, admin_token):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "x", "password": "Test@12345"},
            cookies={"session_token": admin_token},
        )
        # Should not be 401 or 403
        assert response.status_code not in (401, 403)

    def test_org_admin_rejected_with_403(self, client, user_token):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "x", "password": "Test@12345"},
            cookies={"session_token": user_token},
        )
        assert response.status_code == 403

    def test_no_auth_returns_401(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "x", "password": "Test@12345"},
        )
        assert response.status_code == 401

    def test_api_key_treated_as_admin(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "x", "password": "Test@12345"},
            headers={"X-API-KEY": settings.DASHBOARD_API_KEY},
        )
        assert response.status_code not in (401, 403)
