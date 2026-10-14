import json
from types import SimpleNamespace
from unittest.mock import patch

import agent


def _call(arguments='{"section_title": "小學全日制"}', id="c1", name="get_section_last_updated"):
    return SimpleNamespace(id=id, function=SimpleNamespace(name=name, arguments=arguments))


def _run(events, follow_up=("已更新",), trace=None, tool_result=None):
    """Drive answer_question_stream with a scripted model; returns (text, follow_up_messages, tool_mock)."""
    seen_follow_up = []

    def fake_events(messages, tools=None, tool_choice=None):
        yield from events

    def fake_follow_up(messages):
        seen_follow_up.extend(messages)
        yield from follow_up

    with patch("agent.retrieve", return_value=[]), \
         patch("agent._log_trace"), \
         patch("agent.chat_stream_events", side_effect=fake_events), \
         patch("agent.chat_stream", side_effect=fake_follow_up), \
         patch("agent.get_section_last_updated", return_value=tool_result or {"found": True}) as tool:
        text = "".join(agent.answer_question_stream("問題", trace=trace))
    return text, seen_follow_up, tool


def test_first_text_is_yielded_before_the_model_has_finished():
    consumed = []

    def fake_events(messages, tools=None, tool_choice=None):
        for piece in ["第一", "第二", "第三"]:
            consumed.append(piece)
            yield ("text", piece)

    with patch("agent.retrieve", return_value=[]), patch("agent._log_trace"), \
         patch("agent.chat_stream_events", side_effect=fake_events):
        stream = agent.answer_question_stream("問題")
        first = next(stream)

    assert first == "第一"
    assert consumed == ["第一"]


def test_direct_answer_is_joined_and_logged_as_the_final_answer():
    trace = []
    text, _, tool = _run([("text", "第一"), ("text", "第二")], trace=trace)
    assert text == "第一第二"
    tool.assert_not_called()
    assert trace[-1]["event"] == "final_answer"
    assert trace[-1]["answer"] == "第一第二"


def test_tool_call_runs_the_tool_then_streams_the_follow_up():
    trace = []
    text, follow_messages, tool = _run(
        [("tool_calls", [_call()])], follow_up=("已於", "昨日更新"), trace=trace, tool_result={"found": True, "last_updated": "x"}
    )
    assert text == "已於昨日更新"
    tool.assert_called_once_with(section_title="小學全日制")
    assert [m["role"] for m in follow_messages] == ["system", "user", "assistant", "tool"]
    assert follow_messages[2]["tool_calls"][0]["function"]["name"] == "get_section_last_updated"
    assert follow_messages[3]["tool_call_id"] == "c1"
    assert json.loads(follow_messages[3]["content"]) == {"found": True, "last_updated": "x"}
    kinds = [event["event"] for event in trace]
    assert "tool_call_requested" in kinds and "tool_call_result" in kinds


def test_text_written_before_a_tool_call_is_kept_and_separated_from_the_follow_up():
    text, follow_messages, _ = _run([("text", "我查下"), ("tool_calls", [_call()])], follow_up=("答案",))
    assert text == "我查下\n\n答案"
    assert follow_messages[2]["content"] == "我查下"


def test_malformed_tool_arguments_become_a_tool_error_not_a_crash():
    text, follow_messages, tool = _run([("tool_calls", [_call(arguments="{not json")])], follow_up=("照答",))
    assert text == "照答"
    tool.assert_not_called()
    assert "error" in json.loads(follow_messages[3]["content"])


def test_unexpected_tool_arguments_become_a_tool_error_not_a_crash():
    for bad in ('{"wrong": 1}', "[]", '{"section_title": 5}'):
        text, follow_messages, tool = _run([("tool_calls", [_call(arguments=bad)])], follow_up=("照答",))
        assert text == "照答"
        tool.assert_not_called()
        assert "error" in json.loads(follow_messages[3]["content"])


def test_empty_model_reply_yields_nothing():
    text, _, _ = _run([])
    assert text == ""


def test_error_after_the_first_chunk_propagates_to_the_caller():
    def fake_events(messages, tools=None, tool_choice=None):
        yield ("text", "第一")
        raise RuntimeError("connection dropped")

    with patch("agent.retrieve", return_value=[]), patch("agent._log_trace"), \
         patch("agent.chat_stream_events", side_effect=fake_events):
        stream = agent.answer_question_stream("問題")
        assert next(stream) == "第一"
        try:
            next(stream)
        except RuntimeError as exc:
            assert "connection dropped" in str(exc)
        else:
            raise AssertionError("expected the error to propagate")
