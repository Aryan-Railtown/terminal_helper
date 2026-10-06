"""Loads ~/.sage/config.toml and ~/.sage/.env, and builds the configured LLM."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROVIDER = "gemini"
# Lightweight model with free-tier API access. Swap via config.toml or `sage --model`.
DEFAULT_MODEL = "gemini-3.1-flash-lite"

# Provider -> env var holding its API key (None: no key required, e.g. a local server).
KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openai_compatible": None,
}


# Short names for `--model` / config.toml `model = ...`.
MODEL_ALIASES = {
    "flash-lite": ("gemini", DEFAULT_MODEL),
    "gemini": ("gemini", DEFAULT_MODEL),
    "sonnet": ("anthropic", "claude-sonnet-5-5"),
    "opus": ("anthropic", "claude-opus-5-5"),
    "haiku": ("anthropic", "claude-haiku-4-5-20251001"),
    "fable": ("anthropic", "claude-fable-5-1"),
}

# Model id prefix -> provider, for bare ids like "claude-opus-5-5".
_PREFIX_PROVIDER = (("claude-", "anthropic"), ("gemini-", "gemini"), ("gpt-", "openai"))


def resolve_model(spec: str, current_provider: str) -> tuple[str, str]:
    """Turn an alias, `provider:model`, or bare model id into (provider, model)."""
    alias = MODEL_ALIASES.get(spec.strip().lower())
    if alias:
        return alias
    provider, sep, model = spec.partition(":")
    if sep and provider in KEY_ENV:
        return provider, model
    for prefix, prov in _PREFIX_PROVIDER:
        if spec.startswith(prefix):
            return prov, spec
    return current_provider, spec


class ConfigError(Exception):
    """A user-fixable configuration problem; shown as a one-line message."""


@dataclass
class Config:
    home: Path
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    api_base: str | None = None
    api_key_env: str | None = None
    history_turns: int = 6
    history_ttl_minutes: int = 30

    @property
    def history_path(self) -> Path:
        return self.home / "history.json"


def sage_home() -> Path:
    return Path(os.environ.get("SAGE_HOME") or Path.home() / ".sage")


def load_config(home: Path | None = None) -> Config:
    home = Path(home) if home else sage_home()
    data: dict = {}
    path = home / "config.toml"
    if path.exists():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Could not parse {path}: {e}") from e
    known = {"provider", "model", "api_base", "api_key_env", "history_turns", "history_ttl_minutes"}
    cfg = Config(home=home, **{k: v for k, v in data.items() if k in known})
    # An explicit `provider =` wins over model-id prefix guessing (e.g. a gemini-* id behind
    # an openai_compatible proxy); aliases and provider:model still switch it.
    if "provider" not in data or cfg.model.lower() in MODEL_ALIASES or ":" in cfg.model:
        cfg.provider, cfg.model = resolve_model(cfg.model, cfg.provider)
    if cfg.provider not in KEY_ENV:
        raise ConfigError(
            f"Unknown provider {cfg.provider!r} in {path}. Choose one of: {', '.join(KEY_ENV)}."
        )
    if cfg.provider == "openai_compatible" and not cfg.api_base:
        raise ConfigError(f"provider 'openai_compatible' needs api_base set in {path}.")
    return cfg


def load_env(home: Path) -> None:
    """Load API keys from <home>/.env without overriding the real environment."""
    from dotenv import load_dotenv

    load_dotenv(home / ".env", override=False)


def api_key_var(cfg: Config) -> str | None:
    return cfg.api_key_env or KEY_ENV.get(cfg.provider)


def check_api_key(cfg: Config) -> None:
    var = api_key_var(cfg)
    if var and not os.environ.get(var):
        raise ConfigError(
            f"{var} is not set. Add `{var}=...` to {cfg.home / '.env'} or set it in your environment."
        )


def build_llm(cfg: Config):
    import railtracks as rt

    if cfg.provider == "gemini":
        return rt.llm.GeminiLLM(cfg.model)
    if cfg.provider == "anthropic":
        return rt.llm.AnthropicLLM(cfg.model)
    if cfg.provider == "openai":
        return rt.llm.OpenAILLM(cfg.model)
    api_key = os.environ.get(cfg.api_key_env) if cfg.api_key_env else None
    return rt.llm.OpenAICompatibleProvider(cfg.model, api_base=cfg.api_base, api_key=api_key or "none")
