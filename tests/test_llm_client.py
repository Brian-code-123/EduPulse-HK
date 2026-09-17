import threading
from unittest.mock import MagicMock, patch

import llm_client


def test_embedding_model_loaded_exactly_once_under_concurrent_first_access():
    llm_client._embedding_model_instance = None  # reset module-level singleton

    construct_count = 0
    construct_lock = threading.Lock()

    def fake_sentence_transformer(*args, **kwargs):
        nonlocal construct_count
        with construct_lock:
            construct_count += 1
        return MagicMock()

    with patch("llm_client.SentenceTransformer", side_effect=fake_sentence_transformer):
        threads = [threading.Thread(target=llm_client._embedding_model) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert construct_count == 1

    llm_client._embedding_model_instance = None  # cleanup for other tests
