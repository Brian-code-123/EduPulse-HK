import streamlit as st
import streamlit_authenticator as stauth


def require_login() -> None:
    """Render a login form and st.stop() the script if the visitor isn't the
    admin. Must be called before any RAG/API/embedding code runs, so an
    unauthenticated visitor triggers zero backend work."""
    auth_cfg = st.secrets["auth"]

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

    authenticator.login(location="main", max_login_attempts=5)

    if st.session_state.get("authentication_status") is False:
        st.error("用戶名或密碼錯誤")
        st.stop()
    elif st.session_state.get("authentication_status") is None:
        st.info("請登入先可以用小學同行")
        st.stop()

    with st.sidebar:
        st.caption(f"已登入：{st.session_state.get('name')}")
        authenticator.logout("登出", "sidebar")
