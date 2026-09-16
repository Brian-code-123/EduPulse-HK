from functools import lru_cache

from openai import OpenAI
from sentence_transformers import SentenceTransformer

from config import CHAT_MODEL, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, EMBEDDING_MODEL

_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


@lru_cache(maxsize=1)
def _embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def embed(text: str) -> list[float]:
    vector = _embedding_model().encode(text, normalize_embeddings=True)
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
