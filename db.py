from datetime import datetime, timezone

from supabase import Client, create_client

from config import SUPABASE_KEY, SUPABASE_URL

_client: Client | None = None


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
    resp = get_client().rpc(
        "match_document_chunks",
        {"query_embedding": query_embedding, "match_count": match_count},
    ).execute()
    return resp.data or []


def get_snapshot(url: str) -> dict | None:
    resp = get_client().table("page_snapshots").select("*").eq("url", url).execute()
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
