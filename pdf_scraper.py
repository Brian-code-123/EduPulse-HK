import hashlib
import io
import os
import re
import time

import requests
from pypdf import PdfReader

from config import CACHE_DIR, CACHE_TTL_SECONDS, REQUEST_DELAY_SECONDS, USER_AGENT
from scraper import Chunk, split_long_chunk

# PDF text extraction from CJK documents has font/kerning-driven spacing
# quirks that vary by extractor. Verified against the real target PDF with
# pypdf specifically (not assumed from a different tool's output): pypdf
# does NOT insert a space between every CJK glyph, but it DOES incorrectly
# split digit runs — e.g. "2027" comes out as "202 7" or "20 27". Collapse
# spaces between two CJK characters (defensive, in case another PDF hits
# that artifact) and, more importantly here, spaces between two digits.
_CJK_RANGE = "一-鿿　-〿＀-￯"


def normalize_cjk_spacing(text: str) -> str:
    text = re.sub(rf"(?<=[{_CJK_RANGE}])\s+(?=[{_CJK_RANGE}])", "", text)
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    return text


def _pdf_cache_path(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{digest}.pdf")


def fetch_pdf(url: str) -> bytes | None:
    """Fetch a PDF's raw bytes, using a local file cache (keyed by the
    file's own mtime, since binary content can't be JSON-wrapped like
    scraper.fetch_page does for HTML) to avoid hammering the site."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _pdf_cache_path(url)

    if os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_TTL_SECONDS:
        with open(path, "rb") as f:
            return f.read()

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[pdf_scraper] WARNING: failed to fetch {url}: {e}")
        return None
    finally:
        time.sleep(REQUEST_DELAY_SECONDS)

    with open(path, "wb") as f:
        f.write(resp.content)
    return resp.content


def extract_pdf_pages(pdf_bytes: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [normalize_cjk_spacing(page.extract_text() or "") for page in reader.pages]


def extract_pdf_text_from_pages(pages: list[str]) -> str:
    return "\n".join(pages)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    return extract_pdf_text_from_pages(extract_pdf_pages(pdf_bytes))


def chunk_pdf_pages(pages: list[str], url: str, title: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for i, page_text in enumerate(pages, start=1):
        text = page_text.strip()
        if not text:
            continue
        section_title = f"{title} - 第{i}頁"
        for part in split_long_chunk(text):
            chunks.append(Chunk(content=part, url=url, section_title=section_title))
    return chunks


def chunk_pdf(pdf_bytes: bytes, url: str, title: str) -> list[Chunk]:
    return chunk_pdf_pages(extract_pdf_pages(pdf_bytes), url=url, title=title)
