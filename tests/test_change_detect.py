from unittest.mock import patch

from change_detect import check_pdf_url, hash_text
from scraper import extract_page_text


def test_hash_text_differs_when_content_changes():
    original = "小學全日制係自願參加嘅政策。"
    edited = "小學全日制係強制參加嘅政策。"
    assert hash_text(original) != hash_text(edited)


def test_hash_text_same_for_identical_text():
    text = "呢段文字冇改過。"
    assert hash_text(text) == hash_text(text)


def test_normalize_ignores_layout_only_changes():
    html_a = "<html><body><p>小班教學資訊</p></body></html>"
    html_b = "<html><body>\n\n<p>   小班教學資訊   </p>\n\n</body></html>"
    text_a = extract_page_text(html_a)
    text_b = extract_page_text(html_b)
    assert hash_text(text_a) == hash_text(text_b)


def test_normalize_detects_real_text_edit():
    html_a = "<html><body><p>小班教學資訊</p></body></html>"
    html_b = "<html><body><p>小班教學新資訊</p></body></html>"
    text_a = extract_page_text(html_a)
    text_b = extract_page_text(html_b)
    assert hash_text(text_a) != hash_text(text_b)


def test_check_pdf_url_detects_no_change_on_identical_content():
    fake_pdf_bytes = b"fake-pdf-bytes-unchanged"
    with patch("change_detect.fetch_pdf", return_value=fake_pdf_bytes), \
         patch("change_detect.extract_pdf_text", return_value="不變嘅內容"), \
         patch("db.get_snapshot", return_value={"html_hash": hash_text("不變嘅內容"), "raw_text": "不變嘅內容"}), \
         patch("db.upsert_snapshot"):
        result = check_pdf_url("https://example.com/faq.pdf")
    assert result.changed is False


def test_check_pdf_url_detects_change_when_content_differs():
    with patch("change_detect.fetch_pdf", return_value=b"fake-pdf-bytes-changed"), \
         patch("change_detect.extract_pdf_text", return_value="新內容"), \
         patch("db.get_snapshot", return_value={"html_hash": hash_text("舊內容"), "raw_text": "舊內容"}), \
         patch("db.upsert_snapshot"), \
         patch("change_detect.summarize_diff", return_value="內容有變"):
        result = check_pdf_url("https://example.com/faq.pdf")
    assert result.changed is True
    assert result.summary == "內容有變"
