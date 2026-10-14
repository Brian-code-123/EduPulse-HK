from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from config import EDB_URLS
from ui_helpers import STARTERS

SCRIPT = "import ui_chat\nui_chat.render_chat()\n"
KNOWN_URL = EDB_URLS[4]  # whole-day-schooling/index.html


def _stream(text):
    def stream(question, trace=None):
        if trace is not None:
            trace.append({"event": "retrieval_completed", "matched_sections": ["小學全日制"], "similarities": [0.9]})
        for i in range(0, len(text), 4):
            yield text[i : i + 4]

    return stream


def _boom(question, trace=None):
    raise RuntimeError("deepseek down")
    yield  # pragma: no cover


def _empty(question, trace=None):
    return iter(())


def _ask(stream, question, preset=None):
    at = AppTest.from_string(SCRIPT, default_timeout=15)
    with patch("ui_chat.answer_question_stream", side_effect=stream) as agent, patch("ui_chat.record_query") as rec:
        if preset is not None:
            at.session_state["messages"] = preset
        at.run()
        at.chat_input[0].set_value(question).run()
    return at, agent, rec


def test_empty_state_shows_six_starter_buttons():
    at = AppTest.from_string(SCRIPT, default_timeout=15)
    at.run()
    assert not at.exception
    assert [b.label for b in at.button] == STARTERS


def test_clicking_a_starter_asks_it_once_and_clears_pending():
    at = AppTest.from_string(SCRIPT, default_timeout=15)
    with patch("ui_chat.answer_question_stream", side_effect=_stream("答案內容")) as agent, patch("ui_chat.record_query") as rec:
        at.run()
        clicked = at.button[0].label
        at.button[0].click().run()
    assert not at.exception
    assert agent.call_count == 1
    assert agent.call_args.args[0] == clicked
    assert rec.call_count == 1
    assert "pending_question" not in at.session_state
    assert [m["role"] for m in at.session_state["messages"]] == ["user", "assistant"]


def test_whitespace_question_is_ignored():
    at, agent, rec = _ask(_stream("答案"), "   ")
    assert agent.call_count == 0
    assert rec.call_count == 0
    assert at.session_state["messages"] == []


def test_answer_with_known_source_shows_sources_and_records_query():
    answer = f"全日制好處。[小學全日制]({KNOWN_URL})"
    at, agent, rec = _ask(_stream(answer), "全日制有咩好處？")
    assert not at.exception
    message = at.session_state["messages"][-1]
    assert message["sources"] == [("小學全日制", KNOWN_URL)]
    assert message["declined"] is False
    assert rec.call_count == 1
    args = rec.call_args.args
    assert args[0] == "全日制有咩好處？" and args[4] and args[5].tzinfo is not None
    assert any("資料來源" in m.value for m in at.markdown)


def test_generator_raising_shows_friendly_error_and_saves_nothing():
    at, agent, rec = _ask(_boom, "任何問題")
    assert not at.exception
    assert any("暫時未能回答" in e.value for e in at.error)
    assert at.session_state["messages"] == []
    assert rec.call_count == 0


def test_empty_answer_shows_error_and_saves_nothing():
    at, agent, rec = _ask(_empty, "任何問題")
    assert not at.exception
    assert any("暫時未能回答" in e.value for e in at.error)
    assert at.session_state["messages"] == []
    assert rec.call_count == 0


def test_declined_answer_offers_starters_without_repeating_the_question():
    at, agent, rec = _ask(_stream("資料庫中未有相關資訊。"), STARTERS[0])
    assert not at.exception
    labels = [b.label for b in at.button]
    assert len(labels) == 3
    assert STARTERS[0] not in labels
    assert at.session_state["messages"][-1]["declined"] is True


def test_orphan_user_message_is_dropped_on_next_ask():
    preset = [{"role": "user", "content": "被打斷嘅問題"}]
    at, agent, rec = _ask(_stream("答案內容"), "新問題", preset=preset)
    contents = [m["content"] for m in at.session_state["messages"]]
    assert "被打斷嘅問題" not in contents
    assert contents[0] == "新問題"


def test_history_survives_a_rerun():
    at, agent, rec = _ask(_stream("答案內容"), "問題一")
    at.run()
    assert len(at.session_state["messages"]) == 2
    assert len(at.chat_message) == 2
