"""Application configuration — reads from environment variables with sensible defaults."""

import os
from pathlib import Path

# Project root
BASE_DIR = Path(__file__).resolve().parent

# LLM Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-your-api-key-here")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "tickets.db"))

# Data files
TICKETS_JSON = BASE_DIR / "data" / "tickets.json"
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
