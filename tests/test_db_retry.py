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
