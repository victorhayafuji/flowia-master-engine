"""Shared fixtures for the Flowia test suite."""
import os
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("CHECKPOINTER_BACKEND", "memory")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test-whatsapp-app-secret-for-ci")

from packages.auth_core.auth_service import create_access_token

# Stable UUIDs for tenant isolation tests (salon MVP)
ORG_A = "22222222-2222-2222-2222-222222222222"
ORG_B = "33333333-3333-3333-3333-333333333333"

# Stable professional id bound to the professional-role fixtures below.
PROFESSIONAL_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def mock_db(mocker):
    """Mocks the global SupabaseHandler singleton used across the app."""
    mock_handler = mocker.patch("packages.auth_core.database.SupabaseHandler")
    mock_instance = mocker.MagicMock()
    mock_instance.is_ready = True
    mock_handler.return_value = mock_instance

    mocker.patch("packages.auth_core.database.db", mock_instance)
    return mock_instance


@pytest.fixture
def app(mock_db, mocker):
    """Creates a fresh FastAPI app with mocked DB for each test."""
    mocker.patch("apps.salon.api.startup_warmup.is_ready", return_value=True)

    from packages.engine.checkpointer import shutdown_checkpointer

    shutdown_checkpointer()
    from main import create_app

    test_app = create_app()

    test_app.middleware_stack = None
    test_app.user_middleware = [
        m for m in test_app.user_middleware
        if "TrustedHostMiddleware" not in str(m.cls)
    ]
    test_app.middleware_stack = test_app.build_middleware_stack()

    return test_app


@pytest.fixture
def client(app):
    """Returns a TestClient for the app."""
    return TestClient(app)


@pytest.fixture
def admin_token():
    """Generates a valid JWT token with super_admin role."""
    return create_access_token(
        data={"sub": "admin_user"},
        role="super_admin",
        org_id=ORG_A,
    )


@pytest.fixture
def user_token():
    """Generates a valid JWT token with org_admin role (non-admin)."""
    return create_access_token(
        data={"sub": "regular_user"},
        role="org_admin",
        org_id=ORG_A,
    )


@pytest.fixture
def user_token_org_b():
    """Generates a valid JWT token for a user in organization B."""
    return create_access_token(
        data={"sub": "user_org_b"},
        role="org_admin",
        org_id=ORG_B,
    )


@pytest.fixture
def professional_token():
    """JWT for a role=professional user in ORG_A, bound to PROFESSIONAL_A.

    Used to prove employee scoping: agenda/overview filtered to the own
    professional_id, and org_admin-only routes (Patients/Catalog) stay reachable
    at the auth layer but data is scoped (nav-hiding is frontend-only).
    """
    return create_access_token(
        data={"sub": "pro@salao.com"},
        role="professional",
        org_id=ORG_A,
        professional_id=PROFESSIONAL_A,
    )


@pytest.fixture
def expired_token():
    """Generates an expired JWT token."""
    return create_access_token(
        data={"sub": "expired_user"},
        role="super_admin",
        expires_delta=timedelta(seconds=-10),
    )


@pytest.fixture
def mock_admin_user():
    """Returns mock data for a super_admin user record."""
    return {
        "username": "admin_user",
        "role": "super_admin",
        "organization_id": ORG_A,
    }


@pytest.fixture
def mock_regular_user():
    """Returns mock data for a regular org_admin user record."""
    return {
        "username": "regular_user",
        "role": "org_admin",
        "organization_id": ORG_A,
    }


@pytest.fixture
def agent_flow(mocker, mock_db):
    """Simulador multi-turno do Chat Test — ver tests/support/agent_flow.py."""
    from tests.support.agent_flow import AgentFlowConfig, AgentFlowSimulator, install_agent_flow_mocks

    org_table = mocker.MagicMock()
    org_chain = mocker.MagicMock()
    org_chain.select.return_value = org_chain
    org_chain.eq.return_value = org_chain
    org_chain.limit.return_value = org_chain
    org_chain.maybe_single.return_value = org_chain
    org_chain.execute.return_value = mocker.MagicMock(
        data={"name": "Beauty Express"}
    )
    org_table.select.return_value = org_chain

    def _table(name):
        if name == "organizations":
            return org_table
        chain = mocker.MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.maybe_single.return_value = chain
        chain.execute.return_value = mocker.MagicMock(data=[])
        return chain

    mock_db.client.table.side_effect = _table

    def _factory(**overrides):
        cfg = AgentFlowConfig(**overrides)
        install_agent_flow_mocks(mocker, cfg)
        return AgentFlowSimulator(cfg)

    return _factory
