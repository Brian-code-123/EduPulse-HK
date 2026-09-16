# 小學同行

A small grounded Q&A agent for Hong Kong's primary education policy pages on the
[Education Bureau (EDB) website](https://www.edb.gov.hk/tc/edu-system/primary-secondary/primary.html).
Built for a take-home assessment — see `AI_USAGE_NOTE.md` for how AI tools were used.

## What it does

1. **Grounded Q&A** — answers questions using only content scraped from EDB's
   primary-education pages, with inline `[Section Title](URL)` citations. If the
   answer isn't in the indexed pages, it says so instead of guessing.
2. **Agent tool calling** — the LLM can call `get_section_last_updated`, a custom
   tool that looks up when a section was last detected as changed. Tool calls are
   shown live in the "Agent Process Log" panel and logged to `logs/agent_trace.jsonl`.
3. **Change detection** — hashes the normalized text of each tracked page and
   diffs it against the last known snapshot in Supabase.
4. **Push notification** — on a detected change, the diff is summarized in plain
   Cantonese/Chinese by the LLM (no raw HTML) and posted to a Discord webhook.

## Tech stack

- **LLM**: DeepSeek API (`deepseek-flash`, function calling)
- **Embeddings**: local `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim) — runs on your machine, no external embedding API needed
- **Vector store**: Supabase (Postgres + pgvector, HNSW index)
- **UI**: Streamlit
- **Notifications**: Discord webhook

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in:

```
DEEPSEEK_API_KEY=       # https://platform.deepseek.com
SUPABASE_URL=           # your Supabase project URL
SUPABASE_KEY=           # Supabase service_role key (NOT anon) — see security note below
SUPABASE_PROJECT_ID=    # Supabase project ref
DISCORD_WEBHOOK_URL=    # Server Settings → Integrations → Webhooks → Copy URL
```

The Supabase schema (`document_chunks`, `page_snapshots`, `match_document_chunks`
RPC) needs to exist before running — see `supabase_schema.sql` for the DDL used.
Both tables have Row Level Security **enabled with no policies**, so the app
must use the `service_role` key (bypasses RLS, meant for trusted server-side
code — this app never sends it to the browser). The `anon` key is
deliberately left unable to read or write anything.

### Admin login

The app is gated behind a single admin login (`streamlit-authenticator`) —
there's no self-registration. To set it up:

1. Run `python generate_password_hash.py`, type your chosen password, copy the
   printed hash.
2. Add an `[auth]` section to `.streamlit/secrets.toml` (gitignored):
   ```toml
   [auth]
   username = "admin"
   name = "Admin"
   password_hash = "<the hash from step 1>"
   cookie_name = "eduPulseAuth"
   cookie_key = "<any random string, e.g. `python -c \"import secrets; print(secrets.token_hex(16))\"`>"
   cookie_expiry_days = 30
   ```
3. Login is capped at 5 attempts before lockout, and Streamlit's built-in
   error-detail page is disabled (`.streamlit/config.toml`) so failures don't
   leak stack traces.

## Running it

**1. Ingest EDB content into Supabase** (one-off, run whenever you want to
(re)index the source pages):

```bash
python ingest.py
```

This scrapes the 10 hardcoded EDB primary-education URLs (see `config.py`),
chunks and embeds them, writes them to `document_chunks`, and records a
baseline snapshot in `page_snapshots` so change detection has something to
diff against.

**2. Start the app:**

```bash
streamlit run app.py
```

Open the printed local URL. Ask a question in the chat box on the left; the
right-hand panel shows the agent's tool-call trace.

## Triggering the change check

There's no cron in this repo — per the assessment brief, a manual trigger is
fine. Two ways to run it:

- **From the UI**: click "Refresh（檢查EDB網頁有冇更新）" in the app.
- **From the CLI** (e.g. for a real cron job / GitHub Actions schedule):
  ```bash
  python -c "from change_detect import check_updates; from notify import notify_all_changes; notify_all_changes(check_updates())"
  ```

To verify it actually detects a real edit, you can plant a fake old snapshot
and confirm the diff/push fires:

```bash
python -c "
import db, change_detect
url = 'https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/small-class-teaching/index.html'
snap = db.get_snapshot(url)
old_text = snap['raw_text'] + '\n小班教學班級人數上限為25人。'
db.upsert_snapshot(url, change_detect.hash_text(old_text), old_text)
"
python -c "from change_detect import check_updates; from notify import notify_all_changes; notify_all_changes(check_updates())"
python ingest.py  # restores the real baseline afterwards
```

## Tests

```bash
pytest              # unit tests only need no credentials
pytest -m integration  # also exercises live DeepSeek + Supabase (needs ingest.py run first)
```

## Deploying to Streamlit Community Cloud

This app runs fine on Streamlit Community Cloud's free tier — no Docker
needed, and (unlike serverless platforms such as Vercel) it stays a long-lived
process, so the embedding model warms up once and stays warm.

1. Push this repo to GitHub (`.env` and `.streamlit/secrets.toml` are
   gitignored, so keys never leave your machine via git).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, and deploy this repo with `app.py` as the entry point.
3. In the app's **Settings → Secrets**, paste the same keys as your local
   `.env` (`DEEPSEEK_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`,
   `DISCORD_WEBHOOK_URL`) plus the `[auth]` table described above.
4. First deploy takes a few minutes — the image has to install `torch` +
   `sentence-transformers`.

**Known trade-offs of this hosting choice** (see `AI_USAGE_NOTE.md` for the
full write-up): the app sleeps after a period of inactivity and takes
10-60s to wake back up (cold start), which does not match the local
response-time numbers; free-tier RAM is ~1GB, which is tight for
torch+sentence-transformers+Streamlit together.

## Known limitations

See `AI_USAGE_NOTE.md` section 6 for the full honest list (caching, rate
limits, evals, PII, Streamlit Cloud cold starts, what breaks at 20-school
scale). In short: this is a single-tenant demo, not production-ready — one
hardcoded admin account with no self-registration or password reset, no
per-tenant isolation, no retry/backoff on the scraper or LLM calls, and the
hardcoded 10-URL scope means it only knows about pages explicitly listed in
`config.py`.
