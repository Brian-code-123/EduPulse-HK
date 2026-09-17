from scraper import Chunk
from pdf_scraper import chunk_pdf_pages, extract_pdf_text_from_pages, normalize_cjk_spacing


def test_normalize_cjk_spacing_collapses_spaces_between_cjk_chars():
    raw = "2027 年 度 小 一 入 學 統 籌 辦 法"
    assert normalize_cjk_spacing(raw) == "2027 年度小一入學統籌辦法"


def test_normalize_cjk_spacing_preserves_spaces_touching_single_digits():
    # A space between a single digit and a CJK char is left alone — it's
    # a real word boundary, not a rendering artifact.
    raw = "2027 年 9 月 1 日"
    result = normalize_cjk_spacing(raw)
    assert result == "2027 年 9 月 1 日"


def test_normalize_cjk_spacing_collapses_spaces_inside_digit_runs():
    # Real artifact found in pypdf's extraction of the target PDF: digit
    # runs like a year get split mid-number, e.g. "2027" -> "202 7" or
    # "20 27". A space between two digits is never a real word boundary.
    assert normalize_cjk_spacing("202 7 年度") == "2027 年度"
    assert normalize_cjk_spacing("20 27 年 9 月") == "2027 年 9 月"


def test_chunk_pdf_pages_assigns_page_number_to_section_title():
    pages = ["第一頁內容夠長" * 5, "第二頁內容夠長" * 5]
    chunks = chunk_pdf_pages(pages, url="https://example.com/faq.pdf", title="測試FAQ")
    assert chunks[0].section_title == "測試FAQ - 第1頁"
    assert chunks[1].section_title == "測試FAQ - 第2頁"
    assert chunks[0].url == "https://example.com/faq.pdf"


def test_chunk_pdf_pages_skips_empty_pages():
    pages = ["有內容嘅頁面文字內容夠長夠長夠長", "", "   "]
    chunks = chunk_pdf_pages(pages, url="https://example.com/faq.pdf", title="測試FAQ")
    assert len(chunks) == 1


def test_extract_pdf_text_from_pages_joins_with_newline():
    pages = ["第一頁", "第二頁"]
    assert extract_pdf_text_from_pages(pages) == "第一頁\n第二頁"
