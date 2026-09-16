import json
import os
from datetime import datetime, timezone

import db
from config import GUARDRAIL_SYSTEM_PROMPT, TRACE_LOG_PATH
from llm_client import chat, chat_stream
from rag import format_context, retrieve

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_section_last_updated",
            "description": "查詢某個EDB網頁段落(section)最後一次偵測到內容更新嘅時間。當用戶問到資訊係咪最新、幾時更新過，用呢個tool。",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_title": {
                        "type": "string",
                        "description": "要查詢嘅段落標題，例如「小學全日制」",
                    }
                },
                "required": ["section_title"],
            },
        },
    }
]


def _log_trace(event: dict) -> None:
    os.makedirs(os.path.dirname(TRACE_LOG_PATH), exist_ok=True)
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def get_section_last_updated(section_title: str) -> dict:
    resp = (
        db.get_client()
        .table("document_chunks")
        .select("url")
        .ilike("section_title", f"%{section_title}%")
        .limit(1)
        .execute()
    )
    if not resp.data:
        return {"found": False, "message": f"搵唔到段落「{section_title}」"}

    url = resp.data[0]["url"]
    snapshot = db.get_snapshot(url)
    if snapshot is None:
        return {"found": False, "message": "呢個頁面未有偵測記錄"}

    return {
        "found": True,
        "section_title": section_title,
        "url": url,
        "last_updated": snapshot["updated_at"],
    }


def _execute_tool_call(tool_call) -> dict:
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)

    _log_trace({"event": "tool_call_requested", "tool": name, "arguments": args})

    if name == "get_section_last_updated":
        result = get_section_last_updated(**args)
    else:
        result = {"error": f"unknown tool {name}"}

    _log_trace({"event": "tool_call_result", "tool": name, "result": result})
    return result


def _make_logger(trace: list[dict] | None):
    def log(event: dict) -> None:
        _log_trace(event)
        if trace is not None:
            trace.append(event)

    return log


def _retrieve_and_build_messages(question: str, log) -> list[dict]:
    log({"event": "retrieval_started", "query": question})
    chunks = retrieve(question)
    log(
        {
            "event": "retrieval_completed",
            "matched_sections": [c.section_title for c in chunks],
            "similarities": [round(c.similarity, 3) for c in chunks],
        }
    )
    context = format_context(chunks)
    return [
        {"role": "system", "content": GUARDRAIL_SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\n問題：{question}"},
    ]


def _resolve_tool_calls(message, messages: list[dict], trace: list[dict] | None) -> None:
    """Append the assistant's tool-call request and each tool's result to
    `messages` in place, ready for a follow-up chat() call."""
    messages.append(
        {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ],
        }
    )
    for tool_call in message.tool_calls:
        result = _execute_tool_call(tool_call)
        if trace is not None:
            trace.append({"event": "tool_call_requested", "tool": tool_call.function.name})
            trace.append({"event": "tool_call_result", "tool": tool_call.function.name, "result": result})
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )


def answer_question(question: str, trace: list[dict] | None = None) -> str:
    log = _make_logger(trace)
    messages = _retrieve_and_build_messages(question, log)

    log({"event": "llm_call_started", "with_tools": True})
    resp = chat(messages, tools=TOOLS, tool_choice="auto")
    message = resp.choices[0].message

    if message.tool_calls:
        _resolve_tool_calls(message, messages, trace)
        log({"event": "llm_call_started", "with_tools": False, "reason": "final_answer_after_tool"})
        resp = chat(messages)
        message = resp.choices[0].message

    log({"event": "final_answer", "answer": message.content})
    return message.content


def answer_question_stream(question: str, trace: list[dict] | None = None):
    """Generator of answer text chunks, for st.write_stream. Tool-triggered
    answers stream for real from the follow-up LLM call; the direct-answer
    path (no tool needed) is already fully generated by the time we know
    there's no tool call, so it's chunked client-side purely to keep the
    same incremental-display UX."""
    log = _make_logger(trace)
    messages = _retrieve_and_build_messages(question, log)

    log({"event": "llm_call_started", "with_tools": True})
    resp = chat(messages, tools=TOOLS, tool_choice="auto")
    message = resp.choices[0].message

    if message.tool_calls:
        _resolve_tool_calls(message, messages, trace)
        log({"event": "llm_call_started", "with_tools": False, "reason": "final_answer_after_tool", "streamed": True})
        full_text = ""
        for delta in chat_stream(messages):
            full_text += delta
            yield delta
        log({"event": "final_answer", "answer": full_text})
    else:
        text = message.content
        for i in range(0, len(text), 4):
            yield text[i : i + 4]
        log({"event": "final_answer", "answer": text})
