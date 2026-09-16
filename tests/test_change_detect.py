from change_detect import hash_text
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
