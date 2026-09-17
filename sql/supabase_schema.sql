-- EduPulse HK Supabase schema.
-- Applied via Supabase MCP during development; kept here so the schema is
-- reproducible without needing the MCP tool.

create extension if not exists vector;

create table if not exists document_chunks (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  url text not null,
  section_title text not null,
  embedding vector(384) not null,  -- paraphrase-multilingual-MiniLM-L12-v2 output size
  created_at timestamptz not null default now()
);

create index if not exists document_chunks_url_idx on document_chunks (url);
create index if not exists document_chunks_embedding_idx on document_chunks using hnsw (embedding vector_cosine_ops);

create table if not exists page_snapshots (
  id uuid primary key default gen_random_uuid(),
  url text not null unique,
  html_hash text not null,
  raw_text text not null,
  updated_at timestamptz not null default now()
);

create or replace function match_document_chunks(
  query_embedding vector(384),
  match_count int default 3
)
returns table (
  id uuid,
  content text,
  url text,
  section_title text,
  similarity float
)
language sql stable
as $$
  select
    document_chunks.id,
    document_chunks.content,
    document_chunks.url,
    document_chunks.section_title,
    1 - (document_chunks.embedding <=> query_embedding) as similarity
  from document_chunks
  order by document_chunks.embedding <=> query_embedding
  limit match_count;
$$;
