"""Application settings — all overridable via environment variables."""
import logging
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = "AI Music Marketer"
    environment: str = "development"
    # SQLite by default; set APP_DATABASE_URL=postgresql+psycopg2://user:pass@host/db in prod
    database_url: str = "sqlite:///./music_marketer.db"
    cors_origins: str = "http://localhost:3000,http://localhost:8000"
    api_token: str = ""
    auth_user_id: str = "local-artist"
    media_storage_path: str = "./private-media"
    max_upload_bytes: int = 52_428_800
    max_audio_duration_seconds: int = 900
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    ai_provider: str = "mock"
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ai_provider_timeout_seconds: float = 20.0
    ai_provider_max_retries: int = 2
    token_encryption_key: SecretStr = SecretStr("")
    frontend_url: str = "http://localhost:3000"
    youtube_oauth_client_id: str = ""
    youtube_oauth_client_secret: SecretStr = SecretStr("")
    youtube_oauth_redirect_uri: str = ""
    instagram_oauth_client_id: str = ""
    instagram_oauth_client_secret: SecretStr = SecretStr("")
    instagram_oauth_redirect_uri: str = ""
    facebook_oauth_client_id: str = ""
    facebook_oauth_client_secret: SecretStr = SecretStr("")
    facebook_oauth_redirect_uri: str = ""
    meta_graph_api_version: str = "v24.0"
    job_worker_enabled: bool = False  # Disabled for demo performance
    job_poll_interval_seconds: int = 5
    job_idle_timeout_seconds: int = 1800  # 30 minutes for large YouTube uploads
    job_max_attempts: int = 3
    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = 10
    rate_limit_upload_per_hour: int = 20
    rate_limit_analysis_per_hour: int = 10
    # Ollama LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi"
    ollama_enabled: bool = True
    ollama_timeout_seconds: float = 30.0
    # YouTube publishing
    youtube_upload_max_size_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GB (YouTube supports up to 256 GB for verified accounts)
    youtube_publish_rate_limit_per_hour: int = 50
    youtube_publish_mock_mode: bool = False  # Set to True to skip actual YouTube upload for testing
    # Lyric video generation
    lyric_video_max_render_time_seconds: int = 300
    lyric_video_subtitle_format: str = "srt"

    @field_validator("api_token")
    @classmethod
    def validate_api_token(cls, v: str) -> str:
        # In production, enforce that API token is set and strong
        import os
        is_production = os.environ.get("APP_ENVIRONMENT", "").lower() == "production"
        if is_production and (not v or len(v) < 32):
            raise ValueError(
                "APP_API_TOKEN must be set and at least 32 characters long in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    @field_validator("token_encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: SecretStr) -> SecretStr:
        # Warn if encryption key is empty (OAuth tokens will not be encrypted)
        key_str = v.get_secret_value()
        import os
        is_production = os.environ.get("APP_ENVIRONMENT", "").lower() == "production"
        if is_production and not key_str:
            raise ValueError(
                "APP_TOKEN_ENCRYPTION_KEY must be set in production. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()


def configure_logging() -> None:
    """Configure Python stdlib logging with structured format.
    
    Format: ISO timestamp, log level, logger name, and message.
    Use LOG_LEVEL environment variable to override (default: INFO).
    """
    import os
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    
    # Configure root logger
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
    
    # Set backend loggers to INFO (or configured level)
    backend_logger = logging.getLogger("backend")
    backend_logger.setLevel(log_level)


# Initialize logging on module import
configure_logging()
