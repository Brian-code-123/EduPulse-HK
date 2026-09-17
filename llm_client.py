from threading import Lock

from openai import OpenAI
from sentence_transformers import SentenceTransformer

from config import CHAT_MODEL, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, EMBEDDING_MODEL

_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

_embedding_model_instance: SentenceTransformer | None = None
_embedding_model_lock = Lock()


def _embedding_model() -> SentenceTransformer:
    global _embedding_model_instance
    if _embedding_model_instance is None:
        with _embedding_model_lock:
            # Double-checked: another thread may have finished loading while
            # this one was waiting for the lock. Without this second check,
            # two concurrent first-callers would each construct their own
            # SentenceTransformer instance — wasting ~15s twice and briefly
            # doubling memory (~940MB on a 1GB Streamlit Cloud free-tier
            # container, real OOM risk).
            if _embedding_model_instance is None:
                _embedding_model_instance = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model_instance


def embed_query(text: str) -> list[float]:
    """Embed a search query. e5-family models are trained for asymmetric
    query/passage retrieval and need this prefix to use that behaviour —
    without it, the model falls back to generic paraphrase-similarity,
    losing the ranking improvement this migration exists for."""
    vector = _embedding_model().encode(f"query: {text}", normalize_embeddings=True)
    return vector.tolist()


def embed_passage(text: str) -> list[float]:
    """Embed a document chunk for storage. See embed_query for why the
    prefix matters."""
    vector = _embedding_model().encode(f"passage: {text}", normalize_embeddings=True)
    return vector.tolist()


def chat(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None):
    kwargs = {"model": CHAT_MODEL, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    return _client.chat.completions.create(**kwargs)


def chat_stream(messages: list[dict]):
    """Yield content deltas for a tool-free chat completion. Used to improve
    perceived latency in the UI; the caller is responsible for joining the
    deltas into the full answer for logging/return."""
    stream = _client.chat.completions.create(model=CHAT_MODEL, messages=messages, stream=True)
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
