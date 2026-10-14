from datetime import datetime, timezone

from httpx import TransportError
from supabase import Client, create_client

from config import SUPABASE_KEY, SUPABASE_URL

_client: Client | None = None


def _retry_once_on_dropped_connection(call):
    # Supabase closes idle keep-alive connections, so the first request after a
    # quiet spell can fail with "Server disconnected"; the retry opens a fresh one.
    try:
        return call()
    except TransportError:
        return call()


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def delete_chunks_for_url(url: str) -> None:
    get_client().table("document_chunks").delete().eq("url", url).execute()


def insert_chunks(rows: list[dict]) -> None:
    if rows:
        get_client().table("document_chunks").insert(rows).execute()


def match_chunks(query_embedding: list[float], match_count: int) -> list[dict]:
    resp = _retry_once_on_dropped_connection(
        lambda: get_client()
        .rpc("match_document_chunks", {"query_embedding": query_embedding, "match_count": match_count})
        .execute()
    )
    return resp.data or []


def get_snapshot(url: str) -> dict | None:
    resp = _retry_once_on_dropped_connection(
        lambda: get_client().table("page_snapshots").select("*").eq("url", url).execute()
    )
    return resp.data[0] if resp.data else None


def upsert_snapshot(url: str, html_hash: str, raw_text: str) -> None:
    get_client().table("page_snapshots").upsert(
        {
            "url": url,
            "html_hash": html_hash,
            "raw_text": raw_text,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="url",
    ).execute()


def insert_query_log(row: dict) -> None:
    get_client().table("query_log").insert(row).execute()


def get_latest_index_time() -> str | None:
    resp = _retry_once_on_dropped_connection(
        lambda: get_client()
        .table("document_chunks")
        .select("created_at")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0]["created_at"] if resp.data else None


def get_recent_queries(limit: int = 50) -> list[dict]:
    resp = _retry_once_on_dropped_connection(
        lambda: get_client()
        .table("query_log")
        .select("asked_at_hkt,question,declined")
        .order("asked_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def find_chunk_url(section_title: str) -> str | None:
    resp = _retry_once_on_dropped_connection(
        lambda: get_client()
        .table("document_chunks")
        .select("url")
        .ilike("section_title", f"%{section_title}%")
        .limit(1)
        .execute()
    )
    return resp.data[0]["url"] if resp.data else None
