import pytest

from config import EDB_URLS
from scraper import chunk_page, fetch_page

# These URLs are known thin menu/landing pages, kept in EDB_URLS purely so
# the agent can cite the overview page, with their real content covered by
# separate child-page URLs also in EDB_URLS:
# - healthy-sch-policy uses a Webflow accordion whose body text is
#   JS-rendered and unreachable by a static scraper (see AI_USAGE_NOTE.md).
# - small-class-teaching/index.html is a pure link menu; its real content
#   lives in professional-support.html, papers-circulars.html and
#   reference.html, which are separately in EDB_URLS.
KNOWN_THIN_URLS = {
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/healthy-sch-policy/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/small-class-teaching/index.html",
}

MIN_CHARS_FOR_REAL_CONTENT = 50


@pytest.mark.integration
def test_every_edb_url_yields_substantial_content():
    """Regression test for the 'gateway page only, real content one level
    deeper' bug class: direct-subsidy-scheme, through-train and
    small-class-teaching were originally in EDB_URLS pointing at menu pages
    with under 200 chars of real text, so the agent could never answer
    questions about those topics. If a future EDB_URLS entry regresses to a
    menu-only page (e.g. after a site redesign), this test catches it
    instead of relying on someone manually asking the agent every topic."""
    thin_urls = []
    for url in EDB_URLS:
        html = fetch_page(url)
        assert html is not None, f"failed to fetch {url}"
        chunks = chunk_page(html, url)
        total_chars = sum(len(c.content) for c in chunks)
        if url not in KNOWN_THIN_URLS and total_chars < MIN_CHARS_FOR_REAL_CONTENT:
            thin_urls.append((url, total_chars))

    assert not thin_urls, (
        f"these EDB_URLS entries look like menu/gateway pages with no real "
        f"content (add their real content sub-pages, or add to "
        f"KNOWN_THIN_URLS if this is an accepted limitation): {thin_urls}"
    )
