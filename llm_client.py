from threading import Lock
from types import SimpleNamespace

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
                # CPU on purpose: on Apple silicon the default (MPS) aborts the whole
                # process when the warm-up thread and a request encode at once.
                _embedding_model_instance = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
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


def chat_stream_events(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None):
    """Stream one completion. Yields ("text", delta) as it arrives and, only when the
    model asked for tools, a final ("tool_calls", [call, ...]) once every call is
    complete. Tool calls arrive in pieces, so they're assembled here by index."""
    kwargs = {"model": CHAT_MODEL, "messages": messages, "stream": True}
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice

    calls: dict[int, SimpleNamespace] = {}
    for chunk in _client.chat.completions.create(**kwargs):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            yield ("text", delta.content)
        for piece in delta.tool_calls or []:
            call = calls.setdefault(
                piece.index, SimpleNamespace(id="", function=SimpleNamespace(name="", arguments=""))
            )
            if piece.id:
                call.id = piece.id
            if piece.function:
                if piece.function.name:
                    call.function.name = piece.function.name
                if piece.function.arguments:
                    call.function.arguments += piece.function.arguments
    if calls:
        yield ("tool_calls", [calls[index] for index in sorted(calls)])
