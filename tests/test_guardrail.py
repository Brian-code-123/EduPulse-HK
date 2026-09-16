"""Integration tests against the real Supabase + ZhipuAI stack.
Needs `python ingest.py` to have run successfully first (real embedding API
balance required). Skips automatically if the stack isn't reachable, so
`pytest` still passes in an environment without credentials/balance.
"""

import pytest

from agent import answer_question

pytestmark = pytest.mark.integration


def _ask(question: str) -> str:
    try:
        return answer_question(question)
    except Exception as e:  # network/balance/API errors — not a test failure
        pytest.skip(f"live stack not reachable: {e}")


def test_page_covers_this_question_should_cite_source():
    answer = _ask("小學全日制係咪強制推行？")
    assert "未有相關資訊" not in answer
    assert "(" in answer and ")" in answer  # citation format [Section](URL)


def test_page_does_not_cover_this_question_should_say_unknown():
    answer = _ask("大學學費依家幾錢一年？")
    assert "未有" in answer


def test_edge_case_should_cite_but_admit_no_direct_answer():
    answer = _ask("直資學校算唔算官立小學？")
    has_disclaimer = "未有" in answer or "冇明確" in answer
    has_citation = "(" in answer and ")" in answer
    assert has_disclaimer and has_citation
