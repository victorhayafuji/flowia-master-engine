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
