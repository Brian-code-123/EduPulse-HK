from unittest.mock import MagicMock, patch

import db


def _client_returning(data):
    client = MagicMock()
    chain = client.table.return_value.select.return_value.order.return_value.limit.return_value
    chain.execute.return_value.data = data
    return client, chain


def test_get_latest_index_time_returns_newest_created_at():
    client, _ = _client_returning([{"created_at": "2026-09-17T14:50:40+00:00"}])
    with patch("db.get_client", return_value=client):
        assert db.get_latest_index_time() == "2026-09-17T14:50:40+00:00"
    client.table.assert_called_with("document_chunks")
    client.table.return_value.select.return_value.order.assert_called_with("created_at", desc=True)


def test_get_latest_index_time_returns_none_for_empty_table():
    client, _ = _client_returning([])
    with patch("db.get_client", return_value=client):
        assert db.get_latest_index_time() is None


def test_get_recent_queries_orders_by_asked_at_and_limits():
    rows = [{"asked_at_hkt": "2026-10-02 09:30:05.123", "question": "Q", "declined": False}]
    client, chain = _client_returning(rows)
    with patch("db.get_client", return_value=client):
        assert db.get_recent_queries(20) == rows
    client.table.assert_called_with("query_log")
    client.table.return_value.select.return_value.order.assert_called_with("asked_at", desc=True)
    client.table.return_value.select.return_value.order.return_value.limit.assert_called_with(20)


def test_get_recent_queries_returns_empty_list_when_no_data():
    client, _ = _client_returning(None)
    with patch("db.get_client", return_value=client):
        assert db.get_recent_queries() == []
