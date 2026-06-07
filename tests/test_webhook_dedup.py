"""Tests for persistent webhook message deduplication."""
from unittest.mock import MagicMock, patch

from packages.integrations.webhook.dedup import (
    PURGE_JOB_ID,
    purge_stale_entries,
    register_dedup_purge_job,
    try_claim_message,
)


def test_try_claim_message_new_id(mock_db):
    table = MagicMock()
    mock_db.client.table.return_value = table
    table.insert.return_value.execute.return_value = MagicMock(data=[{"message_id": "msg-1"}])

    with patch("packages.integrations.webhook.dedup.db", mock_db):
        assert try_claim_message("msg-1") is True
    table.insert.assert_called_once_with({"message_id": "msg-1"})


def test_try_claim_message_duplicate(mock_db):
    table = MagicMock()
    mock_db.client.table.return_value = table
    table.insert.return_value.execute.side_effect = Exception("duplicate key value violates unique constraint")

    with patch("packages.integrations.webhook.dedup.db", mock_db):
        assert try_claim_message("msg-dup") is False


def test_try_claim_message_empty_id(mock_db):
    assert try_claim_message("") is True


def test_purge_stale_entries_deletes_old_records(mock_db):
    table = MagicMock()
    mock_db.client.table.return_value = table
    delete_chain = MagicMock()
    table.delete.return_value = delete_chain
    delete_chain.lt.return_value = delete_chain
    delete_chain.execute.return_value = MagicMock(
        data=[{"message_id": "old-1"}, {"message_id": "old-2"}]
    )

    with patch("packages.integrations.webhook.dedup.db", mock_db):
        count = purge_stale_entries(retention_days=7)

    assert count == 2
    table.delete.assert_called_once()
    delete_chain.lt.assert_called_once()
    assert delete_chain.lt.call_args[0][0] == "processed_at"


def test_purge_stale_entries_no_client():
    mock_db = MagicMock()
    mock_db.client = None
    with patch("packages.integrations.webhook.dedup.db", mock_db):
        assert purge_stale_entries() == 0


def test_purge_stale_entries_handles_failure(mock_db):
    table = MagicMock()
    mock_db.client.table.return_value = table
    delete_chain = MagicMock()
    table.delete.return_value = delete_chain
    delete_chain.lt.return_value = delete_chain
    delete_chain.execute.side_effect = Exception("connection error")

    with patch("packages.integrations.webhook.dedup.db", mock_db):
        assert purge_stale_entries(retention_days=7) == 0


def test_register_dedup_purge_job():
    scheduler = MagicMock()
    register_dedup_purge_job(scheduler)
    scheduler.add_job.assert_called_once_with(
        purge_stale_entries,
        "cron",
        hour=3,
        minute=0,
        id=PURGE_JOB_ID,
        replace_existing=True,
    )
