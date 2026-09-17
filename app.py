import threading

import streamlit as st

from auth import require_login

st.set_page_config(page_title="小學同行", layout="wide")

CUSTOM_CSS = """
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "PingFang HK", "Noto Sans HK",
                 "Microsoft JhengHei", sans-serif;
}

[data-testid="stChatMessage"] {
    border-radius: 16px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
}

[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    display: none;
}

[data-testid="stChatMessageAvatarUser"] ~ div [data-testid="stChatMessage"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background-color: #F0E6D3;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background-color: #FFFFFF;
    border: 1px solid #EBE1CC;
}

.stButton > button {
    border-radius: 10px;
}

h1, h2, h3 {
    letter-spacing: 0.02em;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Kick off the embedding-model cold load in a background thread *before* the
# login gate. This is safe pre-auth because it's a pure local model load with
# zero DeepSeek/Supabase API calls — it burns no quota, unlike the RAG/agent
# code below, which stays gated behind require_login(). By the time a real
# user finishes typing credentials, the model is likely already warm, so the
# @st.cache_resource call after login mostly just hits the cache instead of
# paying the ~15s cold-load cost.
if "embedding_warmup_started" not in st.session_state:
    st.session_state.embedding_warmup_started = True

    def _background_warmup():
        from llm_client import embed as _embed

        _embed("warm up")

    threading.Thread(target=_background_warmup, daemon=True).start()

require_login()  # must run before any RAG/embedding/API code — see auth.py

from agent import answer_question_stream  # noqa: E402
from change_detect import check_updates  # noqa: E402
from llm_client import embed  # noqa: E402
from notify import notify_all_changes  # noqa: E402

st.title("小學同行")
st.caption("EDB 小學教育問答助手 · 答案有根有據，唔識就話你知")


@st.cache_resource(show_spinner="首次載入 embedding model...")
def _warm_up_embedding_model():
    # If the background thread above already finished loading the model,
    # this call hits llm_client's module-level singleton immediately. If it
    # hasn't, this blocks and loads it here as a fallback (e.g. very fast
    # typers, or an already-warm session where the thread never had to run).
    embed("warm up")
    return True


_warm_up_embedding_model()

if "messages" not in st.session_state:
    st.session_state.messages = []

chat_col, log_col = st.columns([2, 1])

with chat_col:
    st.subheader("問答")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("問關於小學教育嘅問題...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        trace: list[dict] = []
        with st.chat_message("assistant"):
            answer = st.write_stream(answer_question_stream(question, trace=trace))
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.last_trace = trace
        st.rerun()

EVENT_LABELS = {
    "retrieval_started": "搜緊相關內容",
    "retrieval_completed": "搵到相關段落",
    "llm_call_started": "諗緊點答",
    "tool_call_requested": "叫緊個tool",
    "tool_call_result": "Tool答咗嘢返嚟",
    "final_answer": "生成咗答案",
}


def render_trace_event(event: dict) -> None:
    kind = event.get("event", "unknown")
    label = EVENT_LABELS.get(kind, kind)
    with st.expander(label, expanded=False):
        if kind == "retrieval_completed":
            for section, sim in zip(event.get("matched_sections", []), event.get("similarities", [])):
                st.markdown(f"- **{section}**（相似度 {sim}）")
        elif kind == "tool_call_requested":
            st.markdown(f"呼叫 `{event.get('tool')}`")
            if "arguments" in event:
                st.json(event["arguments"])
        elif kind == "tool_call_result":
            st.markdown(f"`{event.get('tool')}` 回傳：")
            st.json(event.get("result", {}))
        elif kind == "final_answer":
            st.markdown(event.get("answer", ""))
        else:
            st.json({k: v for k, v in event.items() if k != "event"})


with log_col:
    st.subheader("Agent Process Log")
    if st.button("Refresh（檢查EDB網頁有冇更新）"):
        with st.spinner("檢查緊..."):
            results = check_updates()
            notify_all_changes(results)
        changed = [r for r in results if r.changed]
        if changed:
            st.success(f"偵測到 {len(changed)} 個頁面有更新，已推送Discord通知")
            for r in changed:
                st.write(f"**{r.url}**")
                st.write(r.summary)
        else:
            st.info("暫時未偵測到任何變更")

    st.divider()
    trace = st.session_state.get("last_trace", [])
    if trace:
        for event in trace:
            render_trace_event(event)
    else:
        st.caption("問一條問題，呢度會顯示Agent嘅執行trace（檢索/tool call/生成過程）")
