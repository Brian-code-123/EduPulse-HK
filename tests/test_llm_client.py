import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np

import llm_client


def test_embedding_model_loaded_exactly_once_under_concurrent_first_access():
    llm_client._embedding_model_instance = None  # reset module-level singleton

    construct_count = 0
    construct_lock = threading.Lock()

    def fake_sentence_transformer(*args, **kwargs):
        nonlocal construct_count
        with construct_lock:
            construct_count += 1
        # Widen the race window: without this, thread start-up overhead
        # alone lets the first thread finish (and populate a cache) before
        # the others even reach the load check, so a broken lru_cache+Lock
        # implementation would falsely pass this test on a typical machine
        # (verified: 10/10 trials showed construct_count == 1 for the
        # broken version without this sleep, vs 5/5 with it).
        time.sleep(0.05)
        return MagicMock()

    with patch("llm_client.SentenceTransformer", side_effect=fake_sentence_transformer):
        threads = [threading.Thread(target=llm_client._embedding_model) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert construct_count == 1

    llm_client._embedding_model_instance = None  # cleanup for other tests


def test_embed_query_prepends_query_prefix(monkeypatch):
    captured = {}

    class FakeModel:
        def encode(self, text, normalize_embeddings=True):
            captured["text"] = text
            return np.array([0.1, 0.2, 0.3])

    monkeypatch.setattr(llm_client, "_embedding_model", lambda: FakeModel())
    llm_client.embed_query("小學全日制嘅好處係咩？")
    assert captured["text"] == "query: 小學全日制嘅好處係咩？"


def test_embed_passage_prepends_passage_prefix(monkeypatch):
    captured = {}

    class FakeModel:
        def encode(self, text, normalize_embeddings=True):
            captured["text"] = text
            return np.array([0.1, 0.2, 0.3])

    monkeypatch.setattr(llm_client, "_embedding_model", lambda: FakeModel())
    llm_client.embed_passage("小學全日制的好處...")
    assert captured["text"] == "passage: 小學全日制的好處..."


def test_embedding_model_is_pinned_to_cpu():
    llm_client._embedding_model_instance = None

    with patch("llm_client.SentenceTransformer") as constructor:
        llm_client._embedding_model()

    assert constructor.call_args.kwargs["device"] == "cpu"
    llm_client._embedding_model_instance = None


def _chunk(content=None, tool_calls=None):
    from types import SimpleNamespace

    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=tool_calls))])


def _tool_delta(index, id=None, name=None, arguments=None):
    from types import SimpleNamespace

    return SimpleNamespace(index=index, id=id, function=SimpleNamespace(name=name, arguments=arguments))


def _events(chunks, **kwargs):
    with patch.object(llm_client._client.chat.completions, "create", return_value=iter(chunks)) as create:
        return list(llm_client.chat_stream_events([{"role": "user", "content": "x"}], **kwargs)), create


def test_chat_stream_events_yields_text_deltas_and_skips_empty_chunks():
    from types import SimpleNamespace

    chunks = [_chunk("你"), _chunk(None), _chunk(""), _chunk("好"), SimpleNamespace(choices=[])]
    events, create = _events(chunks, tools=[{"type": "function"}], tool_choice="auto")
    assert events == [("text", "你"), ("text", "好")]
    kwargs = create.call_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["tools"] == [{"type": "function"}]
    assert kwargs["tool_choice"] == "auto"


def test_chat_stream_events_assembles_tool_call_arguments_across_chunks():
    import json

    chunks = [
        _chunk(tool_calls=[_tool_delta(0, "c1", "get_section_last_updated", '{"section')]),
        _chunk(tool_calls=[_tool_delta(0, None, None, '_title": "小學全日制"}')]),
    ]
    events, _ = _events(chunks)
    assert [kind for kind, _ in events] == ["tool_calls"]
    (call,) = events[0][1]
    assert call.id == "c1"
    assert call.function.name == "get_section_last_updated"
    assert json.loads(call.function.arguments) == {"section_title": "小學全日制"}


def test_chat_stream_events_keeps_interleaved_tool_calls_apart_by_index():
    chunks = [
        _chunk(tool_calls=[_tool_delta(0, "a", "tool_a", '{"x":'), _tool_delta(1, "b", "tool_b", '{"y":')]),
        _chunk(tool_calls=[_tool_delta(1, None, None, "2}"), _tool_delta(0, None, None, "1}")]),
    ]
    events, _ = _events(chunks)
    calls = events[0][1]
    assert [(c.id, c.function.name, c.function.arguments) for c in calls] == [
        ("a", "tool_a", '{"x":1}'),
        ("b", "tool_b", '{"y":2}'),
    ]


def test_chat_stream_events_streams_text_before_a_tool_call_and_puts_tool_calls_last():
    chunks = [_chunk("我查下"), _chunk(tool_calls=[_tool_delta(0, "c1", "t", "{}")])]
    events, _ = _events(chunks)
    assert events[0] == ("text", "我查下")
    assert events[-1][0] == "tool_calls"
