from pathlib import Path

from ui_helpers import (
    FOLLOW_UPS,
    clean_answer,
    STARTERS,
    extract_sources,
    friendly_steps,
    is_declined,
    source_label,
    suggestions,
    topic_of,
)

EVAL_TEXT = (Path(__file__).resolve().parent.parent / "scripts" / "eval.py").read_text(encoding="utf-8")

A = "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/whole-day-schooling/index.html"
B = "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/whole-day-schooling/background/index.html"
KNOWN = {A, B}


def test_extract_sources_dedupes_keeps_order():
    answer = f"[小學全日制]({A}) 同 [背景]({B}) 同 [小學全日制 again]({A})"
    assert extract_sources(answer, KNOWN) == [("小學全日制", A), ("背景", B)]


def test_extract_sources_drops_unknown_url():
    answer = f"[真]({A}) [假](https://evil.example.com/x)"
    assert extract_sources(answer, KNOWN) == [("真", A)]


def test_extract_sources_handles_bracket_in_title_and_no_links():
    assert extract_sources("沒有連結", KNOWN) == []
    assert extract_sources("[A [B]](https://x/a)", KNOWN) == []
    assert extract_sources("[x](https://x/a(1))", KNOWN) == []


def test_is_declined_for_full_and_partial_decline():
    assert is_declined("資料庫中未有相關資訊。")
    assert is_declined("  資料庫中未有直接答案。\n相關資訊如下")
    assert not is_declined("全日制學生每日留校七小時。")


def test_topic_of_maps_each_fragment():
    base = "https://www.edb.gov.hk/tc/edu-system/primary-secondary/"
    cases = {
        "whole-day-schooling/index.html": "全日制",
        "small-class-teaching/index.html": "小班教學",
        "direct-subsidy-scheme/info-sch.html": "直資",
        "through-train/faq-sch.html": "一條龍",
        "primary-1-admission/FAQ_TC.pdf": "小一入學",
        "sbss/index.html": "校本支援",
    }
    for fragment, topic in cases.items():
        assert topic_of([base + fragment]) == topic
    assert topic_of([base + "healthy-sch-policy/index.html"]) is None
    assert topic_of([]) is None


def test_suggestions_excludes_asked_and_caps_at_three():
    asked = FOLLOW_UPS["全日制"][0]
    out = suggestions(f"答案 [x]({A})", asked, KNOWN)
    assert len(out) == 3
    assert asked not in out
    assert len(set(out)) == 3
    assert out[0] == FOLLOW_UPS["全日制"][1]


def test_suggestions_falls_back_to_starters_when_declined_or_unknown_topic():
    declined = suggestions(f"資料庫中未有相關資訊。 [x]({A})", "問過嘅問題", KNOWN)
    assert declined == STARTERS[:3]
    unknown = suggestions("答案，冇引用", "問過嘅問題", KNOWN)
    assert unknown == STARTERS[:3]
    assert STARTERS[0] not in suggestions("資料庫中未有相關資訊。", STARTERS[0], KNOWN)


def test_all_suggestion_questions_exist_in_eval_set():
    questions = list(STARTERS) + [q for qs in FOLLOW_UPS.values() for q in qs]
    missing = [q for q in questions if q not in EVAL_TEXT]
    assert not missing, missing


def test_friendly_steps_variants():
    trace = [
        {"event": "retrieval_completed", "matched_sections": ["小學全日制", "背景"], "similarities": [0.9, 0.88]},
        {"event": "tool_call_requested", "tool": "get_section_last_updated"},
    ]
    steps = friendly_steps(trace)
    assert steps[0] == "搵到 2 段相關內容，最相關係「小學全日制」"
    assert any("最後一次偵測到更新" in s for s in steps)
    assert steps[-1] == "根據搵到嘅內容整理答案"

    no_tool = friendly_steps([{"event": "retrieval_completed", "matched_sections": ["背景"], "similarities": [0.9]}])
    assert not any("最後一次偵測到更新" in s for s in no_tool)

    empty = ["冇搵到夠相關嘅內容"]
    assert friendly_steps([]) == empty
    assert friendly_steps(None) == empty
    assert friendly_steps([{"event": "retrieval_completed", "matched_sections": [], "similarities": []}]) == empty


def test_format_index_date_uses_hong_kong_date_and_tolerates_bad_input():
    from ui_helpers import format_index_date

    assert format_index_date("2026-09-17T14:50:40.123456+00:00") == "2026-09-17"
    assert format_index_date("2026-09-17T17:30:00+00:00") == "2026-09-18"
    assert format_index_date(None) is None
    assert format_index_date("not a date") is None


def test_source_label_prefixes_topic_only_when_known():
    base = "https://www.edb.gov.hk/tc/edu-system/primary-secondary/"
    assert source_label("一般資料", base + "applicable-to-primary-secondary/direct-subsidy-scheme/info-sch.html") == "直資：一般資料"
    assert source_label("小學教育", base + "primary/index.html") == "小學教育"


def test_clean_answer_strips_label_prefix_inside_links_only():
    assert clean_answer("見 [citation:一般資料](https://x/a)。") == "見 [一般資料](https://x/a)。"
    assert clean_answer("[Citation: 背景](https://x/b) 同 [來源：小班](https://x/c)") == "[背景](https://x/b) 同 [小班](https://x/c)"
    assert clean_answer("[一般資料](https://x/a)") == "[一般資料](https://x/a)"
    assert clean_answer("citation: 唔係連結") == "citation: 唔係連結"
