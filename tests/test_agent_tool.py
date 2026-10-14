from unittest.mock import patch

import agent


def test_unknown_section_is_reported_as_not_found():
    with patch("agent.db.find_chunk_url", return_value=None):
        result = agent.get_section_last_updated("冇呢段")
    assert result["found"] is False
    assert "冇呢段" in result["message"]


def test_page_without_a_snapshot_is_reported_as_not_tracked():
    with patch("agent.db.find_chunk_url", return_value="https://x/a"), patch("agent.db.get_snapshot", return_value=None):
        result = agent.get_section_last_updated("小學全日制")
    assert result["found"] is False


def test_known_section_returns_its_url_and_last_update():
    snapshot = {"updated_at": "2026-09-16T10:00:00+00:00"}
    with patch("agent.db.find_chunk_url", return_value="https://x/a"), patch("agent.db.get_snapshot", return_value=snapshot):
        result = agent.get_section_last_updated("小學全日制")
    assert result == {
        "found": True,
        "section_title": "小學全日制",
        "url": "https://x/a",
        "last_updated": "2026-09-16T10:00:00+00:00",
    }
