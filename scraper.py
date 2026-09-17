import copy
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from config import (
    CACHE_DIR,
    CACHE_TTL_SECONDS,
    CHUNK_OVERLAP_CHARS,
    CHUNK_SIZE_CHARS,
    EDB_URLS,
    MAX_CHUNK_CHARS,
    REQUEST_DELAY_SECONDS,
    USER_AGENT,
)

# EDB pages are built on a CMS template where every page injects a huge
# hidden sitemap mega-menu (~1000 lines of unrelated <div> nav, not <nav>)
# before the real content. The actual body text always lives inside this
# fixed container structure, confirmed across all 11 EDB_URLS by manual
# inspection: div.inner_page_content_container > title div + content div.
CONTAINER_CLASS = "inner_page_content_container"
TITLE_CLASS = "generic_inner_page_paragraph_title"
CONTENT_CLASS = "generic_page_content"


@dataclass
class Chunk:
    content: str
    url: str
    section_title: str


def _cache_path(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{digest}.json")


def fetch_page(url: str) -> str | None:
    """Fetch a page's HTML, using a local cache to avoid hammering the site.
    Returns None if the page can't be fetched (404, timeout, etc.)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(url)

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cached = json.load(f)
        if time.time() - cached["fetched_at"] < CACHE_TTL_SECONDS:
            return cached["html"]

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        resp.encoding = "utf-8"  # EDB site doesn't send a charset header; requests defaults to ISO-8859-1
    except requests.RequestException as e:
        print(f"[scraper] WARNING: failed to fetch {url}: {e}")
        return None
    finally:
        time.sleep(REQUEST_DELAY_SECONDS)

    html = resp.text
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"html": html, "fetched_at": time.time()}, f)
    return html


def _clean_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup


def _find_content_containers(soup: BeautifulSoup):
    """Return the page's real-content container divs, skipping the
    site-wide mega-menu junk that surrounds them."""
    return soup.find_all("div", class_=CONTAINER_CLASS)


def extract_page_text(html: str) -> str:
    """Extract normalized plain text from a page, used for change-detection
    hashing. Scoped to the real content containers so the mega-menu (whose
    "hot topics" list changes independently of actual page content) never
    pollutes the hash."""
    soup = _clean_soup(html)
    containers = _find_content_containers(soup)

    if containers:
        text = "\n".join(c.get_text(separator="\n") for c in containers)
    else:
        text = soup.get_text(separator="\n")

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _split_long_chunk(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    parts = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE_CHARS
        parts.append(text[start:end])
        start = end - CHUNK_OVERLAP_CHARS
    return parts


def _chunk_content_block(section_title: str, content_soup, url: str) -> list[Chunk]:
    """Split one container's content into chunks, further breaking it up by
    any h2/h3 sub-headings nested inside, then by length."""
    sub_headings = content_soup.find_all(["h2", "h3"])
    chunks: list[Chunk] = []

    if not sub_headings:
        content = re.sub(r"\n{3,}", "\n\n", content_soup.get_text(separator="\n", strip=True)).strip()
        if content:
            for part in _split_long_chunk(content):
                chunks.append(Chunk(content=part, url=url, section_title=section_title))
        return chunks

    for heading in sub_headings:
        sub_title = f"{section_title} - {heading.get_text(strip=True)}"
        content_parts = []
        for sibling in heading.find_next_siblings():
            if sibling.name in ("h2", "h3"):
                break
            content_parts.append(sibling.get_text(separator="\n", strip=True))
        content = re.sub(r"\n{3,}", "\n\n", "\n".join(p for p in content_parts if p)).strip()
        if not content:
            continue
        for part in _split_long_chunk(content):
            chunks.append(Chunk(content=part, url=url, section_title=sub_title))

    return chunks


def chunk_page(html: str, url: str) -> list[Chunk]:
    """Split a page into chunks scoped to its real content containers
    (see CONTAINER_CLASS). Falls back to a naive whole-page h1/h2/h3 walk
    if the page doesn't follow the expected EDB CMS template."""
    soup = _clean_soup(html)
    containers = _find_content_containers(soup)

    if not containers:
        return _chunk_page_fallback(soup, url)

    chunks: list[Chunk] = []
    for container in containers:
        title_div = container.find(class_=TITLE_CLASS)
        if title_div is None:
            continue
        section_title = title_div.get_text(strip=True)
        if not section_title:
            continue
        # Most EDB pages wrap body content in a `generic_page_content` div,
        # but some template variants (e.g. spa-systems/primary-1-admission)
        # put content directly as siblings of the title div with no wrapper
        # class at all. Fall back to a copy of the container minus its title
        # div in that case, so the title text isn't duplicated into the body.
        content_div = container.find(class_=CONTENT_CLASS)
        if content_div is None:
            content_div = copy.copy(container)
            title_copy = content_div.find(class_=TITLE_CLASS)
            if title_copy is not None:
                title_copy.decompose()
        chunks.extend(_chunk_content_block(section_title, content_div, url))

    return chunks


def _chunk_page_fallback(soup: BeautifulSoup, url: str) -> list[Chunk]:
    main = soup.find("main") or soup.body or soup
    headings = main.find_all(["h1", "h2", "h3"])
    chunks: list[Chunk] = []

    if not headings:
        text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
        title = soup.title.get_text(strip=True) if soup.title else url
        for part in _split_long_chunk(text):
            chunks.append(Chunk(content=part, url=url, section_title=title))
        return chunks

    for heading in headings:
        section_title = heading.get_text(strip=True)
        if not section_title:
            continue
        content_parts = []
        for sibling in heading.find_next_siblings():
            if sibling.name in ("h1", "h2", "h3"):
                break
            content_parts.append(sibling.get_text(separator="\n", strip=True))
        content = re.sub(r"\n{3,}", "\n\n", "\n".join(p for p in content_parts if p)).strip()
        if not content:
            continue
        for part in _split_long_chunk(content):
            chunks.append(Chunk(content=part, url=url, section_title=section_title))

    return chunks


def scrape_all() -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for url in EDB_URLS:
        html = fetch_page(url)
        if html is None:
            continue
        all_chunks.extend(chunk_page(html, url))
    return all_chunks
