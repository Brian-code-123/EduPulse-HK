from scraper import Chunk, chunk_page, extract_page_text, split_long_chunk


def test_split_long_chunk_under_limit_returns_single_part():
    text = "短文字"
    assert split_long_chunk(text) == [text]


def test_split_long_chunk_over_limit_splits_with_overlap():
    text = "a" * 1000
    parts = split_long_chunk(text)
    assert len(parts) > 1
    # overlap: end of first part should reappear at start of second part
    assert parts[0][-150:] == parts[1][:150]


def test_chunk_page_splits_by_heading():
    html = """
    <html><body><main>
    <h2>小班教學</h2>
    <p>呢個係小班教學嘅內容。</p>
    <h2>小學全日制</h2>
    <p>呢個係全日制嘅內容。</p>
    </main></body></html>
    """
    chunks = chunk_page(html, "https://example.com/page.html")
    assert len(chunks) == 2
    assert chunks[0].section_title == "小班教學"
    assert "小班教學嘅內容" in chunks[0].content
    assert chunks[1].section_title == "小學全日制"


def test_chunk_page_splits_long_section_into_multiple_chunks():
    long_paragraph = "呢句會重複好多次。" * 200
    html = f"""
    <html><body><main>
    <h2>長內容段落</h2>
    <p>{long_paragraph}</p>
    </main></body></html>
    """
    chunks = chunk_page(html, "https://example.com/long.html")
    assert len(chunks) > 1
    assert all(c.section_title == "長內容段落" for c in chunks)


def _edb_style_html(title: str, content: str) -> str:
    return f"""
    <html><body>
    <div class="mega_menu">呢度好多junk連結，唔應該入到chunk度<a href="#">熱門資訊</a></div>
    <div class="inner_page_content_container generic">
      <div class="generic_inner_page_paragraph_title">
        <h1 class="generic_inner_page_paragraph_title_h1">{title}</h1>
      </div>
      <div class="generic_page_content">
        <p>{content}</p>
      </div>
    </div>
    </body></html>
    """


def test_chunk_page_scopes_to_content_container_and_skips_mega_menu():
    html = _edb_style_html("小班教學", "呢個係小班教學嘅真正內文。")
    chunks = chunk_page(html, "https://example.com/page.html")
    assert len(chunks) == 1
    assert chunks[0].section_title == "小班教學"
    assert "真正內文" in chunks[0].content
    assert "junk連結" not in chunks[0].content
    assert "熱門資訊" not in chunks[0].content


def test_extract_page_text_scopes_to_content_container():
    html = _edb_style_html("小班教學", "呢個係真正內文。")
    text = extract_page_text(html)
    assert "真正內文" in text
    assert "熱門資訊" not in text
    assert "junk連結" not in text


def test_chunk_page_splits_by_nested_subheading_inside_content_div():
    html = """
    <html><body>
    <div class="inner_page_content_container generic">
      <div class="generic_inner_page_paragraph_title">
        <h1 class="generic_inner_page_paragraph_title_h1">小學全日制</h1>
      </div>
      <div class="generic_page_content">
        <h2>背景</h2>
        <p>背景內容。</p>
        <h2>實踐經驗</h2>
        <p>實踐經驗內容。</p>
      </div>
    </div>
    </body></html>
    """
    chunks = chunk_page(html, "https://example.com/whole-day.html")
    assert len(chunks) == 2
    assert chunks[0].section_title == "小學全日制 - 背景"
    assert "背景內容" in chunks[0].content
    assert chunks[1].section_title == "小學全日制 - 實踐經驗"


def test_extract_page_text_strips_scripts_and_normalizes_whitespace():
    html = """
    <html><body>
    <script>console.log('noise')</script>
    <p>  正文內容   </p>
    <footer>頁尾資訊</footer>
    </body></html>
    """
    text = extract_page_text(html)
    assert "console.log" not in text
    assert "頁尾資訊" not in text
    assert "正文內容" in text
