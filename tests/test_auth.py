"""Tests for auth routes: login, logout, register, change-password."""


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_login_success(self, client, mocker, mock_admin_user):
        mocker.patch(
            "packages.auth_core.auth_router.authenticate_user",
            return_value=mock_admin_user,
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin_user", "password": "Admin@1234"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert "session_token" in response.cookies

    def test_login_invalid_password(self, client, mocker):
        mocker.patch(
            "packages.auth_core.auth_router.authenticate_user",
            return_value=False,
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin_user", "password": "wrong_password"},
        )
        assert response.status_code == 401

    def test_login_unknown_user(self, client, mocker):
        mocker.patch(
            "packages.auth_core.auth_router.authenticate_user",
            return_value=False,
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "ghost", "password": "Ghost@1234"},
        )
        assert response.status_code == 401


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_clears_cookie(self, client):
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"


class TestRegister:
    """Tests for POST /api/v1/auth/register (admin-only)."""

    def test_register_without_auth_returns_401(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "new_user", "password": "Strong@1234"},
        )
        assert response.status_code == 401

    def test_register_with_non_admin_returns_403(self, client, user_token):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "new_user", "password": "Strong@1234"},
            cookies={"session_token": user_token},
        )
        assert response.status_code == 403

    def test_register_with_admin_succeeds(self, client, admin_token, mocker):
        mocker.patch(
            "packages.auth_core.auth_router.get_user_by_username",
            return_value=None,
        )
        mocker.patch(
            "packages.auth_core.auth_router.register_dashboard_user",
            return_value=True,
        )
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "new_user", "password": "Strong@1234"},
            cookies={"session_token": admin_token},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_register_weak_password_returns_422(self, client, admin_token):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "new_user", "password": "weak"},
            cookies={"session_token": admin_token},
        )
        assert response.status_code == 422

    def test_register_no_special_char_returns_422(self, client, admin_token):
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "new_user", "password": "NoSpecial1"},
            cookies={"session_token": admin_token},
        )
        assert response.status_code == 422

    def test_register_duplicate_user_returns_400(self, client, admin_token, mocker, mock_admin_user):
        mocker.patch(
            "packages.auth_core.auth_router.get_user_by_username",
            return_value=mock_admin_user,
        )
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "admin_user", "password": "Strong@1234"},
            cookies={"session_token": admin_token},
        )
        assert response.status_code == 400


class TestChangePassword:
    """Tests for POST /api/v1/auth/change-password."""

    def test_change_password_without_auth_returns_401(self, client):
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Old@1234", "new_password": "New@5678"},
        )
        assert response.status_code == 401

    def test_change_password_weak_new_password_returns_422(self, client, admin_token):
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Admin@1234", "new_password": "weak"},
            cookies={"session_token": admin_token},
        )
        assert response.status_code == 422
