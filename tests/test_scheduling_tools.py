"""Tests for scheduling LangGraph tools."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.runnables import RunnableConfig

from packages.scheduling.tools import _get_org_id_from_config, book_time, check_availability

ORG = "22222222-2222-2222-2222-222222222222"
PATIENT_ID = "33333333-3333-3333-3333-333333333333"
PROF_A = "44444444-4444-4444-4444-444444444444"
PROF_B = "66666666-6666-6666-6666-666666666666"
SVC_ID = "55555555-5555-5555-5555-555555555555"

SERVICE_DATA = {
    "id": SVC_ID,
    "professional_id": PROF_A,
    "duration_minutes": 30,
    "name": "Corte Feminino",
}


class TestOrgIdFromConfig:
    def test_raises_without_org_id(self):
        with pytest.raises(ValueError, match="org_id"):
            _get_org_id_from_config({})

    def test_returns_org_id(self):
        config = RunnableConfig(configurable={"org_id": ORG})
        assert _get_org_id_from_config(config) == ORG


class TestCheckAvailability:
    @pytest.fixture(autouse=True)
    def _rate_limit_ok(self, mocker):
        mocker.patch("packages.scheduling.tools.check_rate_limit", return_value=(True, None))

    @pytest.mark.asyncio
    async def test_service_not_found(self, mocker):
        mocker.patch("packages.scheduling.tools.resolve_service_from_catalog", return_value=(None, "not_found"))

        config = RunnableConfig(configurable={"org_id": ORG})
        result = await check_availability.ainvoke(
            {"service_name": "Corte", "target_date": "2026-06-10"},
            config=config,
        )
        assert "Não encontrei" in result

    @pytest.mark.asyncio
    async def test_returns_grouped_slots_for_multiple_pros(self, mocker):
        mocker.patch("packages.scheduling.tools.resolve_service_from_catalog", return_value=(SERVICE_DATA, None))
        mocker.patch(
            "packages.scheduling.tools.list_eligible_professionals",
            return_value=[
                {"id": PROF_A, "name": "Maria Silva"},
                {"id": PROF_B, "name": "Ana Costa"},
            ],
        )

        mock_sched = MagicMock()

        async def slots_side_effect(professional_id, target_date, service_duration):
            if str(professional_id) == PROF_A:
                return ["2026-06-10T09:00:00", "2026-06-10T10:00:00"]
            return ["2026-06-10T11:00:00"]

        mock_sched.get_available_slots = AsyncMock(side_effect=slots_side_effect)
        mocker.patch("packages.scheduling.tools.SchedulingService", return_value=mock_sched)

        config = RunnableConfig(configurable={"org_id": ORG})
        with patch("packages.scheduling.tools.set_tenant_context"):
            result = await check_availability.ainvoke(
                {"service_name": "Corte", "target_date": "2026-06-10"},
                config=config,
            )

        assert "Maria Silva: 09:00, 10:00" in result
        assert "Ana Costa: 11:00" in result
        assert mock_sched.get_available_slots.await_count == 2

    @pytest.mark.asyncio
    async def test_filters_by_professional_name(self, mocker):
        mocker.patch("packages.scheduling.tools.resolve_service_from_catalog", return_value=(SERVICE_DATA, None))
        mocker.patch(
            "packages.scheduling.tools.list_eligible_professionals",
            return_value=[
                {"id": PROF_A, "name": "Maria Silva"},
                {"id": PROF_B, "name": "Ana Costa"},
            ],
        )

        mock_sched = MagicMock()
        mock_sched.get_available_slots = AsyncMock(return_value=["2026-06-10T14:00:00"])
        mocker.patch("packages.scheduling.tools.SchedulingService", return_value=mock_sched)

        config = RunnableConfig(configurable={"org_id": ORG})
        with patch("packages.scheduling.tools.set_tenant_context"):
            result = await check_availability.ainvoke(
                {
                    "service_name": "Corte",
                    "target_date": "2026-06-10",
                    "professional_name": "Ana",
                },
                config=config,
            )

        assert "Ana Costa: 14:00" in result
        assert "Maria Silva" not in result
        mock_sched.get_available_slots.assert_awaited_once()


class TestBookTime:
    @pytest.fixture(autouse=True)
    def _rate_limit_ok(self, mocker):
        mocker.patch("packages.scheduling.tools.check_rate_limit", return_value=(True, None))

    @pytest.mark.asyncio
    async def test_success_resolves_professional_by_slot(self, mocker):
        mocker.patch(
            "packages.scheduling.tools.upsert_patient_by_phone",
            return_value=PATIENT_ID,
        )
        mocker.patch("packages.scheduling.tools.resolve_service_from_catalog", return_value=(SERVICE_DATA, None))
        mocker.patch(
            "packages.scheduling.tools._resolve_professional_for_datetime",
            new_callable=AsyncMock,
            return_value=PROF_B,
        )

        mock_sched = MagicMock()
        mock_sched.create_appointment = AsyncMock()
        mock_sched._get_org_config.return_value = {"timezone": "America/Sao_Paulo"}
        mocker.patch("packages.scheduling.tools.SchedulingService", return_value=mock_sched)

        config = RunnableConfig(configurable={"org_id": ORG})
        with patch("packages.scheduling.tools.set_tenant_context"):
            result = await book_time.ainvoke(
                {
                    "service_name": "Corte Feminino",
                    "target_datetime": "2026-06-10T14:30:00",
                    "patient_name": "Maria",
                    "patient_phone": "5511999999999",
                    "professional_name": "Ana",
                },
                config=config,
            )

        assert "SUCESSO" in result
        mock_sched.create_appointment.assert_awaited_once()
        appt = mock_sched.create_appointment.await_args.args[0]
        assert str(appt.professional_id) == PROF_B

    @pytest.mark.asyncio
    async def test_unavailable_slot_message(self, mocker):
        mocker.patch(
            "packages.scheduling.tools.upsert_patient_by_phone",
            return_value=PATIENT_ID,
        )
        mocker.patch("packages.scheduling.tools.resolve_service_from_catalog", return_value=(SERVICE_DATA, None))
        mocker.patch(
            "packages.scheduling.tools._resolve_professional_for_datetime",
            new_callable=AsyncMock,
            return_value=None,
        )
        mocker.patch("packages.scheduling.tools.SchedulingService", return_value=MagicMock(_get_org_config=lambda: {"timezone": "America/Sao_Paulo"}))

        config = RunnableConfig(configurable={"org_id": ORG})
        with patch("packages.scheduling.tools.set_tenant_context"):
            result = await book_time.ainvoke(
                {
                    "service_name": "Corte",
                    "target_datetime": "2026-06-10T14:30:00",
                    "patient_name": "Maria",
                    "patient_phone": "5511999999999",
                },
                config=config,
            )

        assert "Horário não disponível" in result


class TestPatientUpsert:
    def test_upsert_patient_by_phone(self, mocker):
        from packages.scheduling.patient_booking import upsert_patient_by_phone

        mock_db = MagicMock()
        mock_db.client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"id": PATIENT_ID}]
        )
        mocker.patch("packages.scheduling.patient_booking.db", mock_db)

        patient_id = upsert_patient_by_phone(ORG, "Maria Silva", "5511999999999")
        assert patient_id == PATIENT_ID
        mock_db.client.table.return_value.upsert.assert_called_once()
