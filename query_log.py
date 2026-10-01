import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import db

DECLINE_PREFIX = "資料庫中未有"
MAX_QUESTION_CHARS = 2000
MAX_ANSWER_CHARS = 20000
HKT = timezone(timedelta(hours=8))  # Hong Kong has no DST
_LINK_RE = re.compile(r"\((https?://[^)\s]+)\)")


def _clean(text: str, limit: int) -> str:
    # Postgres rejects NUL, and JSON/UTF-8 encoding rejects lone surrogates.
    text = text.replace("\x00", "").encode("utf-8", "replace").decode("utf-8")
    return text[:limit]


def build_row(
    question: str,
    answer: str,
    trace: list[dict] | None,
    latency_ms: int,
    session_id: str,
    asked_at: datetime,
) -> dict:
    if asked_at.tzinfo is None:
        raise ValueError("asked_at must be timezone-aware")
    similarities: list[float] = []
    tool_called = False
    for event in trace or []:
        if event.get("event") == "retrieval_completed":
            similarities = event.get("similarities", [])
        elif event.get("event") == "tool_call_requested":
            tool_called = True
    hkt = asked_at.astimezone(HKT)
    return {
        "asked_at": asked_at.astimezone(timezone.utc).isoformat(),
        "asked_at_hkt": f"{hkt:%Y-%m-%d %H:%M:%S}.{hkt.microsecond // 1000:03d}",
        "session_id": session_id,
        "question": _clean(question, MAX_QUESTION_CHARS),
        "answer": _clean(answer, MAX_ANSWER_CHARS),
        "declined": answer.strip().startswith(DECLINE_PREFIX),
        "cited_urls": list(dict.fromkeys(_LINK_RE.findall(answer))),
        "similarities": similarities,
        "tool_called": tool_called,
        "latency_ms": latency_ms,
    }


def log_query(row: dict) -> None:
    # One retry: a Supabase keep-alive connection can go stale between questions.
    for attempt in range(2):
        try:
            db.insert_query_log(row)
            return
        except Exception:
            if attempt == 0:
                time.sleep(1)
            else:
                logging.warning("query_log insert failed", exc_info=True)


def record_query(
    question: str,
    answer: str,
    trace: list[dict] | None,
    latency_ms: int,
    session_id: str,
    asked_at: datetime,
) -> None:
    """Never raises and never blocks: build the row, insert on a daemon thread."""
    try:
        row = build_row(str(question or ""), str(answer or ""), trace, latency_ms, session_id, asked_at)
        threading.Thread(target=log_query, args=(row,), daemon=True).start()
    except Exception:
        logging.warning("query_log record failed", exc_info=True)
