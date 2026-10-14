import logging

import streamlit as st

import db
from change_detect import check_updates
from config import DISCORD_WEBHOOK_URL
from notify import notify_all_changes

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


def _render_refresh() -> None:
    st.subheader("檢查教育局網頁更新")
    if not st.button("Refresh（檢查EDB網頁有冇更新）"):
        return
    try:
        with st.spinner("檢查緊..."):
            results = check_updates()
            notify_all_changes(results)
    except Exception:
        logging.exception("refresh failed")
        st.error("檢查失敗，請稍後再試。")
        return
    changed = [r for r in results if r.changed]
    if not changed:
        st.info("暫時未偵測到任何變更")
        return
    if DISCORD_WEBHOOK_URL:
        st.success(f"偵測到 {len(changed)} 個頁面有更新，已推送Discord通知")
    else:
        st.warning(f"偵測到 {len(changed)} 個頁面有更新，但未設定 Discord webhook，冇推送通知")
    for r in changed:
        st.write(f"**{r.url}**")
        st.write(r.summary)


def _render_recent_queries() -> None:
    st.subheader("最近被問嘅問題")
    try:
        rows = db.get_recent_queries(50)
    except Exception:
        logging.exception("recent queries failed")
        st.caption("暫時讀唔到問答記錄。")
        return
    if not rows:
        st.caption("未有問答記錄。")
        return
    st.dataframe(
        rows,
        hide_index=True,
        column_config={"asked_at_hkt": "時間 (HKT)", "question": "問題", "declined": "拒答"},
    )


def render_admin() -> None:
    st.title("資料更新與除錯")
    st.caption("管理用頁面，一般用戶唔需要用到。")

    _render_refresh()

    st.divider()
    st.subheader("最近一條問題嘅 Agent 過程")
    trace = st.session_state.get("last_trace", [])
    if trace:
        for event in trace:
            render_trace_event(event)
    else:
        st.caption("喺「問答」頁問一條問題，呢度會顯示檢索、tool call 同生成過程。")

    st.divider()
    _render_recent_queries()
