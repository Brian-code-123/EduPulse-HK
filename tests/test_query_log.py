import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from query_log import build_row, log_query, record_query

ASKED = datetime(2026, 10, 2, 1, 30, 5, 123000, tzinfo=timezone.utc)
SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "supabase_schema.sql"


def _row(question="Q?", answer="全日制好處係…", trace=None, asked_at=ASKED):
    return build_row(question, answer, trace, 10, "s", asked_at)


def test_build_row_declined_citations_similarities_tool():
    trace = [
        {"event": "retrieval_completed", "matched_sections": ["a"], "similarities": [0.91, 0.88]},
        {"event": "tool_call_requested", "tool": "get_section_last_updated"},
    ]
    answer = "資料庫中未有直接答案。\n[A](https://x/a) [B](https://x/b) [A again](https://x/a)"
    row = build_row("Q?", answer, trace, 1234, "sess-1", ASKED)
    assert row["declined"] is True
    assert row["cited_urls"] == ["https://x/a", "https://x/b"]
    assert row["similarities"] == [0.91, 0.88]
    assert row["tool_called"] is True
    assert row["latency_ms"] == 1234 and row["session_id"] == "sess-1"


def test_build_row_not_declined_and_no_trace_events():
    row = _row(trace=[])
    assert row["declined"] is False
    assert row["cited_urls"] == []
    assert row["similarities"] == []
    assert row["tool_called"] is False


def test_build_row_truncates():
    row = _row(question="q" * 5000, answer="a" * 50000)
    assert len(row["question"]) == 2000
    assert len(row["answer"]) == 20000


def test_asked_at_hkt_format():
    row = _row()
    assert row["asked_at"] == "2026-10-02T01:30:05.123000+00:00"
    assert row["asked_at_hkt"] == "2026-10-02 09:30:05.123"


def test_asked_at_hkt_midnight_and_year_rollover():
    assert _row(asked_at=datetime(2026, 10, 1, 17, 0, 0, tzinfo=timezone.utc))["asked_at_hkt"] == "2026-10-02 01:00:00.000"
    # 999999 microseconds must truncate to .999, not round up into the next second
    assert _row(asked_at=datetime(2026, 12, 31, 16, 30, 0, 999999, tzinfo=timezone.utc))["asked_at_hkt"] == "2027-01-01 00:30:00.999"


def test_build_row_rejects_naive_asked_at():
    with pytest.raises(ValueError):
        _row(asked_at=datetime(2026, 10, 2, 1, 30, 5))


def test_row_is_json_serializable():
    json.dumps(_row(trace=[{"event": "retrieval_completed", "similarities": [0.9]}]))


def test_build_row_strips_nul_and_bad_unicode():
    row = _row(question="a\x00b\ud800c", answer="x\x00y\ud800z")
    for text in (row["question"], row["answer"]):
        assert "\x00" not in text
        text.encode("utf-8")
    json.dumps(row)


def test_build_row_columns_match_schema():
    block = re.search(r"create table if not exists query_log \((.*?)\n\);", SCHEMA.read_text(), re.S)
    assert block, "query_log table not found in sql/supabase_schema.sql"
    columns = set()
    for line in block.group(1).splitlines():
        line = line.split("--")[0].strip()
        if not line or re.match(r"(primary|constraint|unique|foreign|check)\b", line, re.I):
            continue
        columns.add(line.split()[0])
    assert columns - {"id", "created_at"} == set(_row())


def test_log_query_inserts():
    with patch("query_log.db.insert_query_log") as ins:
        log_query({"k": 1})
        ins.assert_called_once_with({"k": 1})


def test_log_query_retries_once():
    with patch("query_log.db.insert_query_log", side_effect=[RuntimeError("Server disconnected"), None]) as ins, patch("query_log.time.sleep"):
        log_query({"k": 1})
        assert ins.call_count == 2


def test_log_query_swallows_errors():
    with patch("query_log.db.insert_query_log", side_effect=RuntimeError("table missing")) as ins, patch("query_log.time.sleep"):
        log_query({"k": 1})
        assert ins.call_count == 2


def test_record_query_returns_immediately():
    with patch("query_log.db.insert_query_log", side_effect=lambda row: time.sleep(1)):
        t0 = time.time()
        record_query("Q?", "A", [], 5, "s", ASKED)
        assert time.time() - t0 < 0.2


def test_record_query_never_raises():
    with patch("query_log.db.insert_query_log") as ins:
        record_query("Q?", None, None, 5, "s", datetime(2026, 10, 2, 1, 30))  # naive time
        record_query("Q?", None, None, 5, "s", ASKED)  # None answer is coerced, not a crash
        time.sleep(0.2)
        assert ins.call_count == 1
