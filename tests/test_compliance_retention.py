"""Tests for LGPD retention jobs."""
from unittest.mock import MagicMock, patch

from packages.compliance.retention import purge_stale_metrics


def test_purge_stale_metrics(mock_db):
    table = MagicMock()
    table.delete.return_value = MagicMock()
    table.delete.return_value.lt.return_value = table.delete.return_value
    chain = MagicMock()
    chain.lt.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"id": "1"}, {"id": "2"}])
    table.delete.return_value = chain
    mock_db.client.table.return_value = table

    with patch("packages.compliance.retention.db", mock_db):
        removed = purge_stale_metrics(retention_days=365)

    assert removed == 2


def test_purge_stale_metrics_disabled_when_zero(mock_db):
    with patch("packages.compliance.retention.db", mock_db):
        assert purge_stale_metrics(retention_days=0) == 0
