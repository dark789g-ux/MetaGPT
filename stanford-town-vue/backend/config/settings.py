"""Application settings (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend.

    All fields are overridable through environment variables with the
    ``STT_`` prefix (e.g. ``STT_DATABASE_URL``) or a local ``.env`` file.
    """

    database_url: str = "sqlite:///./data/stanford_town.db"
    secret_key_path: str = "~/.stanford-town-vue/secret.key"
    logs_dir: str = "~/.stanford-town-vue/logs"
    assets_dir: str = "./backend/assets"
    frontend_dev_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_prefix="STT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def expanded_secret_key_path(self) -> Path:
        """Return the secret key path with ``~`` expanded to the home directory."""
        return Path(self.secret_key_path).expanduser().resolve()

    def expanded_logs_dir(self) -> Path:
        return Path(self.logs_dir).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()


def bootstrap_secret_key() -> Path:
    """Ensure a Fernet secret key exists on disk; create one if missing.

    Returns the path to the key file. Logs a warning the first time the key
    is generated so the operator can back it up.
    """
    from cryptography.fernet import Fernet

    settings = get_settings()
    key_path = settings.expanded_secret_key_path()
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if not key_path.exists():
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        try:
            key_path.chmod(0o600)
        except OSError:
            # chmod may be a no-op on Windows; ignore.
            pass
        logger.warning(
            "Generated new secret key at {}. BACK THIS UP — losing it makes "
            "encrypted LLM credentials unrecoverable.",
            key_path,
        )
    return key_path
