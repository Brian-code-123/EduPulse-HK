from dataclasses import dataclass

import db
from config import SIMILARITY_THRESHOLD, TOP_K
from llm_client import embed_query


@dataclass
class RetrievedChunk:
    content: str
    url: str
    section_title: str
    similarity: float


def retrieve(query: str, top_k: int = TOP_K, threshold: float = SIMILARITY_THRESHOLD) -> list[RetrievedChunk]:
    query_embedding = embed_query(query)
    rows = db.match_chunks(query_embedding, top_k)
    chunks = [
        RetrievedChunk(
            content=row["content"],
            url=row["url"],
            section_title=row["section_title"],
            similarity=row["similarity"],
        )
        for row in rows
    ]
    return [c for c in chunks if c.similarity >= threshold]


def format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(冇搵到相關內容)"
    blocks = []
    for c in chunks:
        blocks.append(f"[{c.section_title}]({c.url})\n{c.content}")
    return "\n\n---\n\n".join(blocks)
