"""
Application configuration loaded from environment variables / .env file.

Required:
    GROQ_API_KEY    – your free Groq Cloud API key

Optional (have sane defaults):
    GROQ_MODEL            – primary model (default openai/gpt-oss-20b)
    GROQ_FALLBACK_MODEL   – fallback model (default openai/gpt-oss-120b)
    CHROMA_PATH           – where ChromaDB stores its data
    KNOWLEDGE_BASE_PATH   – folder where users drop PDF / TXT files
    DATASETS_PATH         – folder for uploaded CSV/XLSX datasets
    CORS_ORIGINS          – comma-separated list of allowed origins
    LOG_LEVEL             – Python logging level (default INFO)
    VERIFY_ANSWERS        – run self-check after draft answer (default true)
    ROUTER_MAX_TOOLS      – max tools offered to model per turn (default 6)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── project root so relative defaults work wherever the process starts ────
_ROOT = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    """Centralised, validated configuration."""

    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_MODEL")
    groq_fallback_model: str = Field(
        default="openai/gpt-oss-120b", alias="GROQ_FALLBACK_MODEL"
    )

    # ── storage ───────────────────────────────────────────────────────────
    chroma_path: Path = Field(
        default=_ROOT / "data" / "chroma_store", alias="CHROMA_PATH"
    )
    knowledge_base_path: Path = Field(
        default=_ROOT / "data" / "knowledge_base", alias="KNOWLEDGE_BASE_PATH"
    )
    datasets_path: Path = Field(
        default=_ROOT / "data" / "datasets", alias="DATASETS_PATH"
    )

    # ── server ────────────────────────────────────────────────────────────
    cors_origins: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        alias="CORS_ORIGINS",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ── agent ─────────────────────────────────────────────────────────────
    max_agent_iterations: int = Field(default=4, alias="MAX_AGENT_ITERATIONS")
    max_history_messages: int = Field(default=6, alias="MAX_HISTORY_MESSAGES")
    verify_answers: bool = Field(default=True, alias="VERIFY_ANSWERS")
    router_max_tools: int = Field(default=6, alias="ROUTER_MAX_TOOLS")

    # ── validators ────────────────────────────────────────────────────────
    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: object) -> List[str]:
        """Accept a comma-separated string or a list."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, list):
            return [str(o).strip() for o in v if str(o).strip()]
        return ["*"]

    @field_validator("chroma_path", "knowledge_base_path", "datasets_path", mode="after")
    @classmethod
    def ensure_dirs(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v

    # ── convenience ───────────────────────────────────────────────────────
    @property
    def has_groq_key(self) -> bool:
        return bool(self.groq_api_key)

    def configure_logging(self) -> None:
        logging.basicConfig(
            level=self.log_level.upper(),
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )


# Singleton – import from anywhere with `from src.config import settings`
settings = Settings()
settings.configure_logging()
