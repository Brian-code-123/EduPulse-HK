import threading

import streamlit as st

from auth import require_login
from ui_theme import apply_theme

st.set_page_config(page_title="小學同行", layout="centered", initial_sidebar_state="collapsed")
apply_theme()

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
        from llm_client import embed_query as _embed_query

        _embed_query("warm up")

    threading.Thread(target=_background_warmup, daemon=True).start()

require_login()  # must run before any RAG/embedding/API code — see auth.py

import db  # noqa: E402
from config import EDB_URLS, PDF_URLS  # noqa: E402
from llm_client import embed_query  # noqa: E402
from ui_admin import render_admin  # noqa: E402
from ui_chat import render_chat  # noqa: E402
from ui_helpers import format_index_date  # noqa: E402


@st.cache_resource(show_spinner="準備緊問答系統，第一次會慢啲，請稍等…")
def _warm_up_embedding_model():
    # If the background thread above already finished loading the model,
    # this call hits llm_client's module-level singleton immediately. If it
    # hasn't, this blocks and loads it here as a fallback (e.g. very fast
    # typers, or an already-warm session where the thread never had to run).
    embed_query("warm up")
    return True


@st.cache_data(ttl=3600)
def _index_date() -> str | None:
    try:
        return format_index_date(db.get_latest_index_time())
    except Exception:
        return None


def _render_sidebar() -> None:
    with st.sidebar:
        if st.button("重新開始對話"):
            st.session_state.messages = []
            st.session_state.pop("last_trace", None)
            st.session_state.pop("pending_question", None)
            st.rerun()
        st.divider()
        st.markdown("**關於小學同行**")
        st.markdown(
            f"整理自 {len(EDB_URLS)} 個教育局網頁同 {len(PDF_URLS)} 份 PDF，"
            "包括小學全日制、小班教學、直接資助計劃、「一條龍」、小一入學、校本支援、數字教育同健康校園政策。"
        )
        index_date = _index_date()
        if index_date:
            st.caption(f"資料整理日期：{index_date}")
        st.caption("問答會被記錄，用於除錯同改進。")
        st.caption("本服務並非教育局官方服務，內容整理自教育局網頁，只供參考，請以教育局最新公布為準。")


_warm_up_embedding_model()
_render_sidebar()

st.navigation(
    [
        st.Page(render_chat, title="問答", url_path="chat", default=True),
        st.Page(render_admin, title="資料更新與除錯", url_path="admin"),
    ]
).run()
