"""Application configuration — reads from environment variables with sensible defaults."""

import os
from pathlib import Path
from urllib.parse import quote_plus

# Project root
BASE_DIR = Path(__file__).resolve().parent


def get_env(name: str, default: str = "") -> str:
    """Read process env, then Windows User/Machine env when available."""
    value = os.getenv(name)
    if value:
        return value
    if os.name != "nt":
        return default
    try:
        import winreg

        locations = [
            (winreg.HKEY_CURRENT_USER, "Environment"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            ),
        ]
        for root, path in locations:
            try:
                with winreg.OpenKey(root, path) as key:
                    registry_value, _ = winreg.QueryValueEx(key, name)
                if registry_value:
                    return str(registry_value)
            except OSError:
                continue
    except OSError:
        return default
    return default


# LLM Configuration
LLM_BASE_URL = get_env("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = get_env("DEEPSEEK_API_KEY", get_env("LLM_API_KEY", "sk-your-api-key-here"))
LLM_MODEL = get_env("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# PageAgent ReAct LLM proxy. Kept separate from backend business agents so
# browser automation can use Ali/Qwen while business agents keep LLM_*.
PAGE_AGENT_LLM_BASE_URL = get_env(
    "PAGE_AGENT_LLM_BASE_URL",
    get_env("ALI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
)
PAGE_AGENT_LLM_API_KEY = get_env("ALI_API_KEY", "")
PAGE_AGENT_LLM_MODEL = get_env("PAGE_AGENT_LLM_MODEL", "qwen3.7-plus")
PAGE_AGENT_LLM_ALLOWED_MODELS = [
    model.strip()
    for model in os.getenv(
        "PAGE_AGENT_LLM_ALLOWED_MODELS",
        ",".join(
            [
                "qwen3.7-plus",
                "deepseek-v4-flash",
                "qwen3-8b",
                "qwen3-14b",
                "qwen3-30b-a3b",
                "qwen3-30b-a3b-instruct-2507",
                "qwen3-next-80b-a3b-instruct",
                "qwen-plus",
                "qwen-turbo",
                "qwen3.7-max",
                "qwen3.7-max-preview",
                "qwen3.7-max-2026-06-08",
                "qwen3.7-max-2026-05-17",
                "qwen3.5-plus-2026-04-20",
                "qwen3.5-ocr",
                "glm-5.2",
                "kimi-k2.7-code",
            ]
        ),
    ).split(",")
    if model.strip()
]
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
