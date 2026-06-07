"""Tests for salon context helpers."""


class TestGetSalonName:
    def test_fallback_without_org(self):
        from packages.engine.context import get_salon_name

        assert get_salon_name(None) == "seu salão"
        assert get_salon_name("ALL") == "seu salão"

    def test_get_salon_name_from_db(self, mock_db, mocker):
        from packages.engine.context import get_salon_name

        mock_db.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "name": "Salão Beauty Express"
        }

        assert get_salon_name("22222222-2222-2222-2222-222222222222") == "Salão Beauty Express"
