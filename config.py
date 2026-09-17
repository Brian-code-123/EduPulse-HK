import os

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

CHAT_MODEL = "deepseek-flash"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_DIMENSIONS = 384
SIMILARITY_THRESHOLD = 0.85
TOP_K = 5

EDB_URLS = [
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/primary.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/primary/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/small-class-teaching/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/whole-day-schooling/background/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/whole-day-schooling/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/direct-subsidy-scheme/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/it-in-edu/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/sbss/language-learning-support/featurearticle.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/sbss/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/through-train/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/spa-systems/primary-1-admission/index.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/healthy-sch-policy/index.html",
    # --- 以下14條覆蓋原本3個gateway頁面嘅真正子頁內容 ---
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/small-class-teaching/professional-support.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/small-class-teaching/papers-circulars.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/small-class-teaching/reference.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/direct-subsidy-scheme/info-sch.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/direct-subsidy-scheme/useful-materials.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/through-train/background.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/through-train/application-procedures.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/through-train/faq-sch.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/through-train/introduction.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/through-train/faq-parent.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary-secondary/through-train/sch-list.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/whole-day-schooling/general-information-on-the-operation.html",
    "https://www.edb.gov.hk/tc/edu-system/primary-secondary/applicable-to-primary/whole-day-schooling/practice-experience.html",
]

# Tier-2 scope decision: only text-based PDFs are indexed (verified with
# pdftotext that this one extracts real text, not a scan). Scanned PDFs,
# application forms, and posters are explicitly out of scope — see
# AI_USAGE_NOTE.md section 6 for why. Each entry needs a matching title
# below since PDFs don't have an <h1> to scrape a title from.
PDF_URLS = [
    "https://www.edb.gov.hk/attachment/tc/edu-system/primary-secondary/spa-systems/primary-1-admission/FAQ_TC.pdf",
]
PDF_TITLES = {
    "https://www.edb.gov.hk/attachment/tc/edu-system/primary-secondary/spa-systems/primary-1-admission/FAQ_TC.pdf": "小一入學統籌辦法 常見問題",
}

USER_AGENT = "EduPulseHK-research/0.1 (contact: brian0728chun@gmail.com)"
REQUEST_DELAY_SECONDS = 1.0
CACHE_TTL_SECONDS = 24 * 60 * 60
CACHE_DIR = "cache"
TRACE_LOG_PATH = "logs/agent_trace.jsonl"

MAX_CHUNK_CHARS = 800
CHUNK_SIZE_CHARS = 500
CHUNK_OVERLAP_CHARS = 150

GUARDRAIL_SYSTEM_PROMPT = """你係 EDB 專屬助手「小學同行」。你只能根據下面提供嘅 Context 回答問題。
如果 Context 完全冇提及用戶問嘅內容，你必須直接回答「資料庫中未有相關資訊」，唔可以自己創作或推測答案。
如果 Context 有部分相關資訊但冇直接答到條問題，你要老實講「資料庫中未有直接答案」，同時可以列出你搵到嘅相關資訊。
每次回答如果用到 Context 內容，必須喺答案入面用 [Section Title](URL) 格式標明引用嚟源。
"""
