"""Factory that builds the configured LLM provider."""
from __future__ import annotations

from typing import Optional

from dbmask.config import LLMConfig
from dbmask.llm.base import LLMProvider


def create_provider(cfg: LLMConfig) -> Optional[LLMProvider]:
    """Return an :class:`LLMProvider` for the config, or ``None`` if disabled."""
    if not cfg.enabled:
        return None

    provider = (cfg.provider or "openai").lower()
    if provider == "openai":
        from dbmask.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
            timeout=cfg.timeout,
        )
    if provider in ("local", "ollama"):
        from dbmask.llm.local_provider import LocalProvider

        api_style = (cfg.api_style or "ollama").lower()
        if api_style not in ("ollama", "openai"):
            raise ValueError(
                f"Unknown llm.api_style: {cfg.api_style!r} (expected 'ollama' or 'openai')"
            )
        return LocalProvider(
            model=cfg.model,
            base_url=cfg.base_url or "http://localhost:11434",
            temperature=cfg.temperature,
            timeout=cfg.timeout,
            api_style=api_style,
        )
    raise ValueError(f"Unknown LLM provider: {cfg.provider!r}")
