"""Tests for scheduling LangGraph tools."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.runnables import RunnableConfig

from packages.scheduling.tools import _get_org_id_from_config, _resolve_professional_id, book_time, check_availability

ORG = "22222222-2222-2222-2222-222222222222"
PATIENT_ID = "33333333-3333-3333-3333-333333333333"
PROF_ID = "44444444-4444-4444-4444-444444444444"
SVC_ID = "55555555-5555-5555-5555-555555555555"


class TestOrgIdFromConfig:
    def test_raises_without_org_id(self):
        with pytest.raises(ValueError, match="org_id"):
            _get_org_id_from_config({})

    def test_returns_org_id(self):
        config = RunnableConfig(configurable={"org_id": ORG})
        assert _get_org_id_from_config(config) == ORG


class TestResolveProfessional:
    def test_uses_service_professional_id(self):
        assert _resolve_professional_id(ORG, {"professional_id": "prof-1"}) == "prof-1"

    def test_falls_back_to_first_active(self, mocker):
        mock_db = MagicMock()
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "prof-fallback"}]
        )
        mocker.patch("packages.scheduling.tools.db", mock_db)
        assert _resolve_professional_id(ORG, {}) == "prof-fallback"


class TestCheckAvailability:
    @pytest.mark.asyncio
    async def test_service_not_found(self, mocker):
        mock_db = MagicMock()
        mock_db.client.table.return_value.select.return_value.eq.return_value.ilike.return_value.execute.return_value = MagicMock(
            data=[]
        )
        mocker.patch("packages.scheduling.tools.db", mock_db)

        config = RunnableConfig(configurable={"org_id": ORG})
        result = await check_availability.ainvoke(
            {"service_name": "Corte", "target_date": "2026-06-10"},
            config=config,
        )
        assert "Não encontrei" in result

    @pytest.mark.asyncio
    async def test_returns_formatted_slots(self, mocker):
        mock_db = MagicMock()
        mock_db.client.table.return_value.select.return_value.eq.return_value.ilike.return_value.execute.return_value = MagicMock(
            data=[{
                "id": SVC_ID,
                "professional_id": PROF_ID,
                "duration_minutes": 30,
                "name": "Corte Feminino",
            }]
        )
        mocker.patch("packages.scheduling.tools.db", mock_db)

        mock_sched = MagicMock()
        mock_sched.get_available_slots = AsyncMock(return_value=["2026-06-10T09:00:00", "2026-06-10T09:30:00"])
        mocker.patch("packages.scheduling.tools.SchedulingService", return_value=mock_sched)

        config = RunnableConfig(configurable={"org_id": ORG})
        with patch("packages.scheduling.tools.set_tenant_context"):
            result = await check_availability.ainvoke(
                {"service_name": "Corte", "target_date": "2026-06-10"},
                config=config,
            )

        assert "09:00" in result
        assert "Corte Feminino" in result
        mock_sched.get_available_slots.assert_awaited_once()
        call_kwargs = mock_sched.get_available_slots.await_args.kwargs
        assert call_kwargs["professional_id"] == PROF_ID
        assert call_kwargs["target_date"] == date(2026, 6, 10)


class TestBookTime:
    @pytest.mark.asyncio
    async def test_success_creates_appointment(self, mocker):
        patient_chain = MagicMock()
        patient_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": PATIENT_ID}]
        )

        service_chain = MagicMock()
        service_chain.select.return_value.eq.return_value.ilike.return_value.execute.return_value = MagicMock(
            data=[{
                "id": SVC_ID,
                "professional_id": PROF_ID,
                "duration_minutes": 45,
                "name": "Coloração",
            }]
        )

        mock_db = MagicMock()
        mock_db.client.table.side_effect = lambda name: patient_chain if name == "patients" else service_chain
        mocker.patch("packages.scheduling.tools.db", mock_db)

        mock_sched = MagicMock()
        mock_sched.create_appointment = AsyncMock()
        mocker.patch("packages.scheduling.tools.SchedulingService", return_value=mock_sched)

        config = RunnableConfig(configurable={"org_id": ORG})
        with patch("packages.scheduling.tools.set_tenant_context"):
            result = await book_time.ainvoke(
                {
                    "service_name": "Coloração",
                    "target_datetime": "2026-06-10T14:30:00",
                    "patient_name": "Maria",
                    "patient_phone": "5511999999999",
                },
                config=config,
            )

        assert "SUCESSO" in result
        mock_sched.create_appointment.assert_awaited_once()
