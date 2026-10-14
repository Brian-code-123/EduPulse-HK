import re
from collections.abc import Iterable
from datetime import datetime

from query_log import DECLINE_PREFIX, HKT

STARTERS = [
    "全日制小學學生一般每日喺學校留幾多個鐘？",
    "政府由邊個學年開始喺公營小學推行小班教學？",
    "直資計劃係邊一年開始推行㗎？",
    "一條龍學校嘅小六學生使唔使參加升中派位？",
    "細路幾多歲先可以申請小一入學統籌辦法？",
    "校本支援服務分為邊三大類？",
]

FOLLOW_UPS = {
    "全日制": [
        "全日制小學學生一般每日喺學校留幾多個鐘？",
        "香港大約有幾多間全日制小學？",
        "政府幾時開始逐步推行小學全日制？",
    ],
    "小班教學": [
        "政府由邊個學年開始喺公營小學推行小班教學？",
        "教師參加小班教學嘅科目工作坊，一共有幾多小時？",
        "「促進實踐社群」支援計劃最少會提供幾多小時專業支援？",
    ],
    "直資": [
        "直資學校收幾多學費先仲可以攞到全額政府津貼？",
        "直資學校最少要拎幾多學費收入做學費減免同獎助學金？",
        "直資計劃係邊一年開始推行㗎？",
    ],
    "一條龍": [
        "一條龍中學最少要預留幾多中一學額俾其他小學嘅學生？",
        "一條龍學校有邊幾種配對模式？",
        "兩間學校想結為一條龍，申請時要交啲咩文件？",
    ],
    "小一入學": [
        "遞交小一入學申請要帶啲咩證明文件？",
        "自行分配學位階段，家長幾時可以攞小一入學申請表？",
        "小一入學電子平台個網址係乜？",
    ],
    "校本支援": [
        "校本支援服務分為邊三大類？",
        "教育局人員提供嘅校本支援服務有邊幾個組？",
        "香港嘅語文教育政策想學生達到咩能力？",
    ],
}

_TOPIC_BY_URL_FRAGMENT = [
    ("whole-day-schooling", "全日制"),
    ("small-class-teaching", "小班教學"),
    ("direct-subsidy-scheme", "直資"),
    ("through-train", "一條龍"),
    ("primary-1-admission", "小一入學"),
    ("sbss", "校本支援"),
]

_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_LABEL_PREFIX_RE = re.compile(r"\[(?:citation|source|引用|來源|出處)\s*[:：]\s*", re.IGNORECASE)
NO_CONTENT = "冇搵到夠相關嘅內容"


def clean_answer(answer: str) -> str:
    """The model sometimes writes [citation:Title](url) instead of [Title](url)."""
    return _LABEL_PREFIX_RE.sub("[", answer)


def is_declined(answer: str) -> bool:
    return answer.strip().startswith(DECLINE_PREFIX)


def extract_sources(answer: str, known_urls: set[str]) -> list[tuple[str, str]]:
    sources: dict[str, str] = {}
    for title, url in _LINK_RE.findall(answer):
        if url in known_urls:
            sources.setdefault(url, title)
    return [(title, url) for url, title in sources.items()]


def source_label(title: str, url: str) -> str:
    topic = topic_of([url])
    return f"{topic}：{title}" if topic else title


def topic_of(urls: Iterable[str]) -> str | None:
    for url in urls:
        for fragment, topic in _TOPIC_BY_URL_FRAGMENT:
            if fragment in url:
                return topic
    return None


def suggestions(answer: str, asked: str, known_urls: set[str]) -> list[str]:
    topic = None
    if not is_declined(answer):
        topic = topic_of(url for _, url in extract_sources(answer, known_urls))
    pool = FOLLOW_UPS.get(topic, []) + STARTERS
    return list(dict.fromkeys(q for q in pool if q != asked))[:3]


def friendly_steps(trace: list[dict] | None) -> list[str]:
    sections: list[str] = []
    tool_called = False
    for event in trace or []:
        if event.get("event") == "retrieval_completed":
            sections = event.get("matched_sections", [])
        elif event.get("event") == "tool_call_requested":
            tool_called = True
    if not sections:
        return [NO_CONTENT]
    steps = [f"搵到 {len(sections)} 段相關內容，最相關係「{sections[0]}」"]
    if tool_called:
        steps.append("查詢咗呢個段落最後一次偵測到更新嘅時間")
    steps.append("根據搵到嘅內容整理答案")
    return steps


def format_index_date(created_at: str | None) -> str | None:
    if not created_at:
        return None
    try:
        return datetime.fromisoformat(created_at).astimezone(HKT).strftime("%Y-%m-%d")
    except ValueError:
        return None
