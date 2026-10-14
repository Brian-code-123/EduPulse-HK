from unittest.mock import MagicMock, patch

import db


def test_match_chunks_retries_once_after_dropped_connection():
    import httpx

    client = MagicMock()
    execute = client.rpc.return_value.execute
    execute.side_effect = [httpx.RemoteProtocolError("Server disconnected"), MagicMock(data=[{"content": "x"}])]
    with patch("db.get_client", return_value=client):
        assert db.match_chunks([0.1] * 3, 5) == [{"content": "x"}]
    assert execute.call_count == 2


def test_match_chunks_gives_up_after_second_transport_error():
    import httpx
    import pytest

    client = MagicMock()
    client.rpc.return_value.execute.side_effect = httpx.RemoteProtocolError("Server disconnected")
    with patch("db.get_client", return_value=client):
        with pytest.raises(httpx.RemoteProtocolError):
            db.match_chunks([0.1] * 3, 5)
    assert client.rpc.return_value.execute.call_count == 2


def test_match_chunks_does_not_retry_non_transport_errors():
    import pytest

    client = MagicMock()
    client.rpc.return_value.execute.side_effect = ValueError("bad query")
    with patch("db.get_client", return_value=client):
        with pytest.raises(ValueError):
            db.match_chunks([0.1] * 3, 5)
    assert client.rpc.return_value.execute.call_count == 1


def test_get_snapshot_retries_once_after_dropped_connection():
    import httpx

    client = MagicMock()
    execute = client.table.return_value.select.return_value.eq.return_value.execute
    execute.side_effect = [httpx.RemoteProtocolError("Server disconnected"), MagicMock(data=[{"url": "u"}])]
    with patch("db.get_client", return_value=client):
        assert db.get_snapshot("u") == {"url": "u"}
    assert execute.call_count == 2


def _flaky(execute_mock, data):
    import httpx

    execute_mock.side_effect = [httpx.RemoteProtocolError("Server disconnected"), MagicMock(data=data)]


def test_get_latest_index_time_retries_once_after_dropped_connection():
    client = MagicMock()
    execute = client.table.return_value.select.return_value.order.return_value.limit.return_value.execute
    _flaky(execute, [{"created_at": "2026-09-17T14:50:40+00:00"}])
    with patch("db.get_client", return_value=client):
        assert db.get_latest_index_time() == "2026-09-17T14:50:40+00:00"
    assert execute.call_count == 2


def test_get_recent_queries_retries_once_after_dropped_connection():
    client = MagicMock()
    execute = client.table.return_value.select.return_value.order.return_value.limit.return_value.execute
    _flaky(execute, [{"question": "Q"}])
    with patch("db.get_client", return_value=client):
        assert db.get_recent_queries(5) == [{"question": "Q"}]
    assert execute.call_count == 2


def test_find_chunk_url_returns_the_url_or_none_and_retries_once():
    client = MagicMock()
    execute = client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute
    _flaky(execute, [{"url": "https://x/a"}])
    with patch("db.get_client", return_value=client):
        assert db.find_chunk_url("小學全日制") == "https://x/a"
    client.table.assert_called_with("document_chunks")
    client.table.return_value.select.return_value.ilike.assert_called_with("section_title", "%小學全日制%")
    assert execute.call_count == 2

    client = MagicMock()
    client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value.data = []
    with patch("db.get_client", return_value=client):
        assert db.find_chunk_url("冇呢段") is None
