import streamlit as st

# Contrast (WCAG AA needs 4.5): text #2B2B26 on #FAF6EE 13.2; caption #6B6458 on #FAF6EE 5.4;
# white on primary #965616 5.8; primary link on #FAF6EE 5.4.
CSS = """
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "PingFang HK", "Noto Sans HK",
                 "Microsoft JhengHei", sans-serif;
}

.block-container {
    padding-top: 0.5rem;
    padding-bottom: 1rem;
}

[data-testid="stVerticalBlock"] {
    gap: 0.45rem;
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

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background-color: #F0E6D3;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background-color: #FFFFFF;
    border: 1px solid #EBE1CC;
}

.stButton > button {
    border-radius: 10px;
    min-height: 2.5rem;
    height: auto;
    padding: 0.35rem 0.9rem;
}

.stButton > button > div {
    width: 100%;
    justify-content: flex-start;
}

.stButton > button p {
    font-size: 0.95rem;
    line-height: 1.4;
    text-align: left;
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
}

[data-testid="stCaptionContainer"] {
    color: #6B6458;
}

[data-testid="stMarkdownContainer"] a {
    color: #965616;
}

[data-testid="stHeaderActionElements"] {
    display: none;
}

h1 {
    font-size: 1.7rem !important;
    padding-bottom: 0.25rem;
}

h2 {
    font-size: 1.4rem !important;
}

h3 {
    font-size: 1.15rem !important;
}

h1, h2, h3 {
    letter-spacing: 0.02em;
}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
