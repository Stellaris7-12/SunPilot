"""Application configuration — reads from environment variables with sensible defaults."""

import os
from pathlib import Path
from urllib.parse import quote_plus

# Project root
BASE_DIR = Path(__file__).resolve().parent

# LLM Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-your-api-key-here")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# PageAgent ReAct LLM proxy. Kept separate from backend business agents so
# browser automation can use Ali/Qwen while business agents keep LLM_*.
PAGE_AGENT_LLM_BASE_URL = os.getenv(
    "PAGE_AGENT_LLM_BASE_URL",
    os.getenv("ALI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
)
PAGE_AGENT_LLM_API_KEY = os.getenv("ALI_API_KEY", "")
PAGE_AGENT_LLM_MODEL = os.getenv("PAGE_AGENT_LLM_MODEL", "qwen3.7-plus")
PAGE_AGENT_LLM_TIMEOUT = int(os.getenv("PAGE_AGENT_LLM_TIMEOUT", str(LLM_TIMEOUT)))

# Database
SUPPORTED_DB_BACKENDS = {"mysql", "tdsql"}
DB_BACKEND = os.getenv("DB_BACKEND", "mysql").lower()


def _default_mysql_url(database_name: str = "ticket_agent") -> str:
    password = os.getenv("MYSQL_ROOT_PASSWORD", "")
    if not password:
        return ""
    escaped_password = quote_plus(password)
    return f"mysql+asyncmy://root:{escaped_password}@127.0.0.1:3306/{database_name}?charset=utf8mb4"


DATABASE_URL = os.path.expandvars(os.getenv("DATABASE_URL", "")) or _default_mysql_url()
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_TIMEOUT_SECONDS = int(os.getenv("DB_TIMEOUT_SECONDS", "30"))
DB_SSL_ENABLED = os.getenv("DB_SSL_ENABLED", "false").lower() in {"1", "true", "yes"}


def validate_database_config():
    if DB_BACKEND not in SUPPORTED_DB_BACKENDS:
        supported = ", ".join(sorted(SUPPORTED_DB_BACKENDS))
        raise RuntimeError(f"Unsupported DB_BACKEND={DB_BACKEND!r}. Supported values: {supported}.")
    if not DATABASE_URL:
        raise RuntimeError(
            "MySQL DATABASE_URL is required. Set MYSQL_ROOT_PASSWORD for the local root "
            "connection or provide DATABASE_URL explicitly."
        )
    if "sqlite" in DATABASE_URL.lower():
        raise RuntimeError("SQLite DATABASE_URL is no longer supported; use MySQL/TDSQL.")
    if "${" in DATABASE_URL or "$MYSQL_ROOT_PASSWORD" in DATABASE_URL:
        raise RuntimeError("DATABASE_URL still contains an unresolved MYSQL_ROOT_PASSWORD placeholder.")

# Data files
TICKETS_JSON = BASE_DIR / "data" / "tickets.json"
CALL_TRANSCRIPTS_JSON = BASE_DIR / "data" / "call_transcripts.json"
AGENT_CARDS_JSON = BASE_DIR / "data" / "agent_cards.json"
TOOLS_JSON = BASE_DIR / "data" / "tools.json"
TRACES_DIR = BASE_DIR / "data" / "traces"

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# Agent defaults
DEFAULT_AGENT_TIMEOUT = int(os.getenv("DEFAULT_AGENT_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "1"))
