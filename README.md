# 小學同行

A grounded Q&A agent over Hong Kong's EDB primary-education policy pages — ask it a question, it answers from indexed source pages with inline citations, and says "I don't know" instead of making something up when a page doesn't cover it.

## Contents

- [Overview](#overview)
- [Demo](#demo)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Deployment](#deployment)

## Overview

Parents and teachers looking up EDB policy — whole-day schooling, direct subsidy scheme, P1 admission — currently have to dig through a maze of HTML pages and PDFs on the EDB site. This app indexes that content once and lets you ask it directly, in Cantonese, with every answer traceable back to the page it came from.

Four things it does:

1. **Grounded Q&A** — retrieves relevant chunks from Supabase pgvector, feeds them to DeepSeek as context, and requires the model to cite `[Section Title](URL)` for anything it states. If nothing relevant is in the index, it says so rather than guessing.
2. **Agent tool calling** — the LLM can call `get_section_last_updated` to check when a section last changed, and the call is visible live in the sidebar, not hidden behind the scenes.
3. **Change detection** — hashes each tracked page's normalized text and diffs it against the last snapshot stored in Supabase.
4. **Push notifications** — when a page changes, DeepSeek summarizes the diff in plain Cantonese and posts it to a Discord webhook, so nobody has to read a raw HTML diff.

**Stack**: Streamlit for the UI, DeepSeek (`deepseek-flash`) for generation and tool calling, a local `sentence-transformers` model (`intfloat/multilingual-e5-small`) for embeddings, Supabase (Postgres + pgvector) for storage and retrieval, Discord webhooks for notifications.

## Demo

![Website demo](assets/website-demo.gif)

Grounded Q&A (in-domain, out-of-domain, and an edge-case question), the tool-call trace, and a detected page change pushed to Discord — all in one recording.

## Quick start

**Requirements**: Python 3.11+, a Supabase project, a DeepSeek API key, a Discord webhook URL (optional, only needed for push notifications).

```bash
git clone <this repo>
cd EduPulse-HK
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your keys (see [Configuration](#configuration) below), then create the Supabase schema:

```bash
psql "$SUPABASE_DB_URL" -f sql/supabase_schema.sql
# or paste sql/supabase_schema.sql into the Supabase SQL editor
```

Ingest the source pages, then run the app:

```bash
python ingest.py       # scrapes EDB pages + the whitelisted PDF, embeds and stores chunks
streamlit run app.py
```

Open the URL Streamlit prints. First load is slower than usual — the embedding model has to load into memory once.

## Configuration

`.env`:

```
DEEPSEEK_API_KEY=       # https://platform.deepseek.com
SUPABASE_URL=           # your Supabase project URL
SUPABASE_KEY=           # service_role key — not anon, see note below
SUPABASE_PROJECT_ID=    # Supabase project ref
DISCORD_WEBHOOK_URL=    # Server Settings → Integrations → Webhooks → Copy URL
```

`document_chunks` and `page_snapshots` have Row Level Security enabled with no policies, so reads and writes only work through the `service_role` key — the `anon` key is deliberately left unable to touch either table. This app runs entirely server-side (Streamlit), so `service_role` never reaches a browser.

The source page list lives in `config.py` (`EDB_URLS`, `PDF_URLS`) rather than a database table — adding a page to track means adding a URL there and re-running `ingest.py`.

## Usage

Ask a question in the chat box. The right-hand "Agent Process Log" panel shows what the agent actually did to answer it — retrieval, similarity scores, the generation step — so you can see it's not just printing canned text.

To check EDB pages for updates and push a Discord notification on anything that changed:

```bash
python -c "from change_detect import check_updates; from notify import notify_all_changes; notify_all_changes(check_updates())"
```

or click "Refresh（檢查EDB網頁有冇更新）" in the app. There's no scheduler wired up here — run this from cron, a GitHub Actions schedule, or by hand.

## Project structure

```
app.py             Streamlit UI — chat, login gate, agent trace panel, refresh button
rag.py              retrieval: embeds the query, calls Supabase's match_document_chunks RPC
agent.py            DeepSeek tool-calling loop, get_section_last_updated tool
llm_client.py       DeepSeek chat client + embed_query/embed_passage (asymmetric e5 prefixes)
scraper.py           HTML fetch + chunking for EDB pages
pdf_scraper.py        PDF fetch + per-page chunking (pypdf)
ingest.py           one-off pipeline: scrape/extract → chunk → embed → store in Supabase
change_detect.py     hash + diff each tracked page against its last snapshot
notify.py             posts a change summary to the Discord webhook
db.py                 Supabase client + query helpers
config.py             source URLs, model names, thresholds, prompts
sql/supabase_schema.sql   table + RPC definitions
tests/                 unit tests (mocked) + integration tests (live DeepSeek/Supabase)
```

Ingestion, change detection, and notifications are independent of the Streamlit request path and share no state with it beyond the Supabase client — you can run `ingest.py` or the change check from a plain script without touching the app.

## Testing

```bash
pytest                   # unit tests, no credentials needed
pytest -m integration    # exercises live DeepSeek + Supabase, needs ingest.py run first
```

## Deployment

Runs as-is on Streamlit Community Cloud's free tier — push to GitHub, deploy from [share.streamlit.io](https://share.streamlit.io) with `app.py` as the entry point, and paste the same keys from `.env` into the app's Secrets. First deploy takes a few minutes to install `torch` + `sentence-transformers`.

The free tier sleeps the app after inactivity (10-60s cold start on the next visit) and caps RAM around 1GB, which is tight but workable for this model's footprint.
