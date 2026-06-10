"""Health must respond fast for Render (5s probe); warmup runs in background."""
import time

import pytest
from httpx import ASGITransport, AsyncClient

from apps.salon.api.app_factory import create_salon_app


@pytest.mark.asyncio
async def test_health_responds_before_warmup_completes(mocker):
    async def slow_warmup():
        import asyncio

        await asyncio.sleep(60)

    mocker.patch(
        "apps.salon.api.startup_warmup._run_warmup",
        side_effect=slow_warmup,
    )

    app = create_salon_app()
    transport = ASGITransport(app=app)
    headers = {"Host": "localhost"}

    async with app.router.lifespan_context(app):
        start = time.perf_counter()
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            resp = await client.get("/health")
        elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["ready"] is False
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_api_returns_503_until_warmup_ready(mocker):
    mocker.patch("apps.salon.api.startup_warmup.start_background_warmup")
    mocker.patch("apps.salon.api.startup_warmup.is_ready", return_value=False)

    app = create_salon_app()
    transport = ASGITransport(app=app)
    headers = {"Host": "localhost"}

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            health = await client.get("/health")
            blocked = await client.get("/api/v1/auth/me")

    assert health.status_code == 200
    assert blocked.status_code == 503
