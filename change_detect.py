import difflib
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

import db
from config import EDB_URLS
from llm_client import chat
from scraper import extract_page_text, fetch_page


@dataclass
class ChangeResult:
    url: str
    changed: bool
    summary: str | None = None
    detected_at: str | None = None


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def summarize_diff(url: str, old_text: str, new_text: str) -> str:
    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            lineterm="",
            n=1,
        )
    )
    diff_text = "\n".join(diff_lines)[:4000]

    prompt = f"""以下係 {url} 呢頁教育局網頁嘅內容變更（diff格式，+號係新增，-號係刪除）：

{diff_text}

請用一兩句白話中文（唔准夾雜HTML標籤）總結呢次變更講咩，畀無技術背景嘅家長/教師都睇得明。"""

    resp = chat([{"role": "user", "content": prompt}])
    return resp.choices[0].message.content.strip()


def check_url(url: str) -> ChangeResult:
    html = fetch_page(url)
    if html is None:
        return ChangeResult(url=url, changed=False)

    new_text = extract_page_text(html)
    new_hash = hash_text(new_text)

    snapshot = db.get_snapshot(url)
    if snapshot is None:
        db.upsert_snapshot(url, new_hash, new_text)
        return ChangeResult(url=url, changed=False)

    if snapshot["html_hash"] == new_hash:
        return ChangeResult(url=url, changed=False)

    summary = summarize_diff(url, snapshot["raw_text"], new_text)
    detected_at = datetime.now(timezone.utc).isoformat()
    db.upsert_snapshot(url, new_hash, new_text)
    return ChangeResult(url=url, changed=True, summary=summary, detected_at=detected_at)


def check_updates() -> list[ChangeResult]:
    return [check_url(url) for url in EDB_URLS]
