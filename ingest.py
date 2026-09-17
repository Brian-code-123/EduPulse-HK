"""One-off CLI script: scrape EDB pages, embed chunks, load into Supabase,
then write a baseline page_snapshots row for each URL so change detection
has something to diff against on the first refresh.

Usage: python ingest.py
"""

import db
from change_detect import check_pdf_url, check_url
from config import EDB_URLS, PDF_TITLES, PDF_URLS
from llm_client import embed_passage
from pdf_scraper import chunk_pdf, fetch_pdf
from scraper import scrape_all


def main() -> None:
    print("[ingest] scraping EDB pages...")
    chunks = scrape_all()
    print(f"[ingest] got {len(chunks)} chunks from {len(EDB_URLS)} URLs")

    print("[ingest] scraping PDF documents...")
    pdf_chunks = []
    for url in PDF_URLS:
        pdf_bytes = fetch_pdf(url)
        if pdf_bytes is None:
            continue
        pdf_chunks.extend(chunk_pdf(pdf_bytes, url, PDF_TITLES.get(url, url)))
    print(f"[ingest] got {len(pdf_chunks)} chunks from {len(PDF_URLS)} PDFs")

    chunks = chunks + pdf_chunks

    for url in EDB_URLS + PDF_URLS:
        db.delete_chunks_for_url(url)

    rows = []
    for i, chunk in enumerate(chunks):
        embedding = embed_passage(chunk.content)
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
    for url in PDF_URLS:
        check_pdf_url(url)
    print("[ingest] done")


if __name__ == "__main__":
    main()
