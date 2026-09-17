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
