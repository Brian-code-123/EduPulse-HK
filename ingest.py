"""One-off CLI script: scrape EDB pages, embed chunks, load into Supabase,
then write a baseline page_snapshots row for each URL so change detection
has something to diff against on the first refresh.

Usage: python ingest.py
"""

import db
from change_detect import check_url
from config import EDB_URLS
from llm_client import embed
from scraper import scrape_all


def main() -> None:
    print("[ingest] scraping EDB pages...")
    chunks = scrape_all()
    print(f"[ingest] got {len(chunks)} chunks from {len(EDB_URLS)} URLs")

    for url in EDB_URLS:
        db.delete_chunks_for_url(url)

    rows = []
    for i, chunk in enumerate(chunks):
        embedding = embed(chunk.content)
        rows.append(
            {
                "content": chunk.content,
                "url": chunk.url,
                "section_title": chunk.section_title,
                "embedding": embedding,
            }
        )
        print(f"[ingest] embedded {i + 1}/{len(chunks)}: {chunk.section_title[:30]}")

    db.insert_chunks(rows)
    print(f"[ingest] inserted {len(rows)} chunks into document_chunks")

    print("[ingest] writing baseline snapshots for change detection...")
    for url in EDB_URLS:
        check_url(url)
    print("[ingest] done")


if __name__ == "__main__":
    main()
