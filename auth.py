import streamlit as st
import streamlit_authenticator as stauth


def require_login() -> None:
    """Render a login form and st.stop() the script if the visitor isn't the
    admin. Must be called before any RAG/API/embedding code runs, so an
    unauthenticated visitor triggers zero backend work."""
    auth_cfg = st.secrets["auth"]

    header = st.empty()
    with header.container():
        st.title("小學同行")
        st.caption("教育局小學教育資料問答，答案附出處")

    authenticator = stauth.Authenticate(
        credentials={
            "usernames": {
                auth_cfg["username"]: {
                    "name": auth_cfg.get("name", auth_cfg["username"]),
                    "password": auth_cfg["password_hash"],
                }
            }
        },
        cookie_name=auth_cfg["cookie_name"],
        cookie_key=auth_cfg["cookie_key"],
        cookie_expiry_days=float(auth_cfg.get("cookie_expiry_days", 30)),
    )

    authenticator.login(
        location="main",
        max_login_attempts=5,
        fields={
            "Form name": "登入小學同行",
            "Username": "用戶名稱",
            "Password": "密碼",
            "Login": "登入",
            "Captcha": "驗證碼",
        },
    )

    if st.session_state.get("authentication_status") is False:
        st.error("用戶名或密碼錯誤")
        st.stop()
    elif st.session_state.get("authentication_status") is None:
        st.info("請先登入")
        st.stop()

    header.empty()

    with st.sidebar:
        st.caption(f"已登入：{st.session_state.get('name')}")
        authenticator.logout("登出", "sidebar")
