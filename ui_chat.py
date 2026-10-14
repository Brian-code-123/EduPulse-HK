import logging
import time
import uuid
from datetime import datetime, timezone
from itertools import chain

import streamlit as st

from agent import answer_question_stream
from config import EDB_URLS, PDF_URLS
from query_log import record_query
from ui_helpers import STARTERS, clean_answer, extract_sources, friendly_steps, is_declined, source_label, suggestions

KNOWN_URLS = set(EDB_URLS) | set(PDF_URLS)
EDB_PRIMARY_URL = "https://www.edb.gov.hk/tc/edu-system/primary-secondary/primary/index.html"
MAX_QUESTION_CHARS = 500


def _init_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("session_id", uuid.uuid4().hex)
    st.session_state.setdefault("pending_question", None)


def _suggestion_buttons(questions: list[str], key_prefix: str) -> None:
    for j, question in enumerate(questions):
        if st.button(question, key=f"{key_prefix}_{j}", use_container_width=True):
            st.session_state.pending_question = question
            st.rerun()


def _render_empty_state() -> None:
    st.caption("揀一條問題開始，或者直接問")
    _suggestion_buttons(STARTERS, "starter")


def _render_extras(index: int, message: dict, is_last: bool) -> None:
    if message["sources"]:
        st.markdown("**資料來源**")
        for title, url in message["sources"]:
            st.markdown(f"- [{source_label(title, url)}]({url}) · 教育局網頁")
    with st.expander("呢個答案係點樣搵到嘅"):
        for step in message["steps"]:
            st.markdown(f"- {step}")
    if message["declined"]:
        st.markdown(f"如果答案唔夠啱，可以試下以下問題，或者直接睇[教育局小學教育網頁]({EDB_PRIMARY_URL})。")
    if is_last and message["suggestions"]:
        st.markdown("**你可能想問**")
        _suggestion_buttons(message["suggestions"], f"suggest_{index}")


def _render_history(messages: list[dict]) -> None:
    for i, message in enumerate(messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_extras(i, message, is_last=i == len(messages) - 1)


def _ask(question: str) -> None:
    messages = st.session_state.messages
    asked_at = datetime.now(timezone.utc)
    if messages and messages[-1]["role"] == "user":
        messages.pop()  # left over from an interrupted run
    messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    trace: list[dict] = []
    started = time.time()
    with st.chat_message("assistant"):
        try:
            with st.status("搜尋緊相關資料同整理答案…") as status:
                stream = answer_question_stream(question, trace=trace)
                first = next(stream, None)
                if first is None:
                    raise RuntimeError("empty answer")
                status.update(label="已搵到資料", state="complete")
            raw_answer = st.write_stream(chain([first], stream))
        except Exception:
            logging.exception("answering failed")
            messages.pop()
            st.error("暫時未能回答，請稍後再試。")
            return

    answer = clean_answer(raw_answer)
    messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": extract_sources(answer, KNOWN_URLS),
            "steps": friendly_steps(trace),
            "suggestions": suggestions(answer, question, KNOWN_URLS),
            "declined": is_declined(answer),
        }
    )
    st.session_state.last_trace = trace
    record_query(question, raw_answer, trace, int((time.time() - started) * 1000), st.session_state.session_id, asked_at)
    st.rerun()


def render_chat() -> None:
    _init_state()
    messages = st.session_state.messages
    pending = st.session_state.pop("pending_question", None)

    st.title("小學同行")

    typed = st.chat_input("問一條問題（問答會被記錄）", max_chars=MAX_QUESTION_CHARS)
    question = (typed or pending or "").strip()

    # The slot replaces last run's starter buttons at once, instead of leaving them
    # greyed out under the first answer while it streams.
    slot = st.empty()
    if not messages and not question:
        with slot.container():
            _render_empty_state()
    else:
        _render_history(messages)

    if question:
        _ask(question)
