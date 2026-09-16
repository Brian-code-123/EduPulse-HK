from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from change_detect import ChangeResult
from config import DISCORD_WEBHOOK_URL

EMBED_COLOR = int("C97C3D", 16)  # matches the app's theme primaryColor


def _format_hk_time(iso_timestamp: str) -> str:
    dt = datetime.fromisoformat(iso_timestamp).astimezone(ZoneInfo("Asia/Hong_Kong"))
    period = "上午" if dt.hour < 12 else "下午"
    hour_12 = dt.hour % 12 or 12
    return f"{dt.year}年{dt.month}月{dt.day}日 {period}{hour_12}:{dt.minute:02d}"


def send_change_notification(result: ChangeResult) -> None:
    if not DISCORD_WEBHOOK_URL:
        print("[notify] DISCORD_WEBHOOK_URL not set, skipping push")
        return

    embed = {
        "title": "小學同行 · 偵測到頁面更新",
        "description": result.summary,
        "color": EMBED_COLOR,
        "fields": [
            {"name": "頁面", "value": result.url, "inline": False},
            {"name": "偵測時間", "value": _format_hk_time(result.detected_at), "inline": False},
        ],
        "footer": {"text": "小學同行 自動監測"},
    }
    resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
    resp.raise_for_status()


def notify_all_changes(results: list[ChangeResult]) -> None:
    for result in results:
        if result.changed:
            send_change_notification(result)
