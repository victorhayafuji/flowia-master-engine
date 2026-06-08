"""Tests for save_conversation_metric observability fields."""
from packages.engine.metrics.service import save_conversation_metric


def test_save_conversation_metric_includes_observability_fields(mocker):
    mock_table = mocker.Mock()
    mock_table.insert.return_value.execute.return_value = mocker.Mock()
    mock_client = mocker.Mock()
    mock_client.table.return_value = mock_table
    mocker.patch("packages.engine.metrics.service.db.client", mock_client)

    save_conversation_metric(
        thread_id="t1",
        sender_id="t1",
        agent_type="scheduling",
        messages_count=4,
        tokens_in=0,
        tokens_out=0,
        tokens_total=0,
        organization_id="22222222-2222-2222-2222-222222222222",
        scheduling_path="deterministic",
        triage_source="keyword",
        channel="chat_test",
        tools_called=[],
    )

    payload = mock_table.insert.call_args[0][0]
    assert payload["organization_id"] == "22222222-2222-2222-2222-222222222222"
    assert payload["scheduling_path"] == "deterministic"
    assert payload["triage_source"] == "keyword"
    assert payload["channel"] == "chat_test"
    assert payload["tools_called"] == []


def test_get_scheduling_observability_counts_paths(mocker):
    rows = [
        {"scheduling_path": "deterministic", "channel": "chat_test", "tokens_total": 0, "agent_type": "scheduling"},
        {"scheduling_path": "llm", "channel": "whatsapp", "tokens_total": 120, "agent_type": "scheduling"},
        {"scheduling_path": None, "channel": "chat_test", "tokens_total": 50, "agent_type": "receptionist"},
    ]

    class FluentQuery:
        def select(self, *_args, **_kwargs):
            return self

        def gte(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            return mocker.Mock(data=rows)

    mock_client = mocker.Mock()
    mock_client.table.return_value = FluentQuery()
    mocker.patch("packages.engine.metrics.service.db.wait_for_ready", return_value=True)
    mocker.patch("packages.engine.metrics.service.db.client", mock_client)

    from packages.engine.metrics.service import get_scheduling_observability

    result = get_scheduling_observability(days=7)

    assert result["scheduling_turns"] == 2
    assert result["deterministic_count"] == 1
    assert result["llm_count"] == 1
    assert result["deterministic_rate_pct"] == 50.0
    assert result["by_channel"]["chat_test"] == 2
    assert result["by_channel"]["whatsapp"] == 1


def test_get_scheduling_observability_channel_filter(mocker):
    rows = [
        {"scheduling_path": "deterministic", "channel": "chat_test", "tokens_total": 0, "agent_type": "scheduling"},
    ]

    class FluentQuery:
        def select(self, *_args, **_kwargs):
            return self

        def gte(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            return mocker.Mock(data=rows)

    mock_client = mocker.Mock()
    mock_client.table.return_value = FluentQuery()
    mocker.patch("packages.engine.metrics.service.db.wait_for_ready", return_value=True)
    mocker.patch("packages.engine.metrics.service.db.client", mock_client)

    from packages.engine.metrics.service import get_scheduling_observability

    result = get_scheduling_observability(days=7, channel="chat_test")

    assert result["channel_filter"] == "chat_test"
    assert result["scheduling_turns"] == 1
