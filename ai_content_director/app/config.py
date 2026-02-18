"""Application configuration via Pydantic Settings and ENV."""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Bảng giá tĩnh (USD per 1M tokens) cho cost guard. Có thể override bằng env.
DEFAULT_OPENAI_INPUT_PRICE_PER_1M = 0.15   # gpt-4o-mini input
DEFAULT_OPENAI_OUTPUT_PRICE_PER_1M = 0.60  # gpt-4o-mini output


class Settings(BaseSettings):
    """App settings loaded from environment and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_content_director",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # OpenAI (planner + content generation). Thiếu OPENAI_API_KEY thì tự fallback template.
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_timeout_seconds: int = Field(default=45, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_retries: int = Field(default=2, alias="OPENAI_MAX_RETRIES")
    openai_temperature: float = Field(default=0.7, alias="OPENAI_TEMPERATURE")
    # Cost guard: daily budget per tenant (USD). Vượt → fallback template, không gọi OpenAI.
    daily_budget_usd: float = Field(default=2.0, alias="DAILY_BUDGET_USD")
    # Giá USD / 1M tokens (tùy chọn; không set thì dùng DEFAULT_*).
    openai_input_price_per_1m: Optional[float] = Field(default=None, alias="OPENAI_INPUT_PRICE_PER_1M")
    openai_output_price_per_1m: Optional[float] = Field(default=None, alias="OPENAI_OUTPUT_PRICE_PER_1M")
    # Rate limit: requests per minute per tenant (hoặc api_key). Cần REDIS_URL.
    rate_limit_per_min: int = Field(default=60, alias="RATE_LIMIT_PER_MIN")
    # Facebook Graph API (chỉ đăng bài đã approved).
    facebook_page_id: Optional[str] = Field(default=None, alias="FACEBOOK_PAGE_ID")
    facebook_access_token: Optional[str] = Field(default=None, alias="FACEBOOK_ACCESS_TOKEN")
    facebook_api_version: str = Field(default="v20.0", alias="FACEBOOK_API_VERSION")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    # Google Drive dropzone (Service Account + folder IDs)
    gdrive_sa_key_path: Optional[str] = Field(default=None, alias="GDRIVE_SA_KEY_PATH")
    gdrive_ready_folder_id: Optional[str] = Field(default=None, alias="GDRIVE_READY_FOLDER_ID")
    gdrive_processed_folder_id: Optional[str] = Field(default=None, alias="GDRIVE_PROCESSED_FOLDER_ID")
    gdrive_rejected_folder_id: Optional[str] = Field(default=None, alias="GDRIVE_REJECTED_FOLDER_ID")
    local_media_dir: str = Field(default="/opt/aiplatform/media_cache", alias="LOCAL_MEDIA_DIR")
    asset_max_size_mb: int = Field(default=50, alias="ASSET_MAX_SIZE_MB")
    asset_allowed_mime_image: str = Field(
        default="image/jpeg,image/png,image/webp",
        alias="ASSET_ALLOWED_MIME_IMAGE",
    )
    asset_allowed_mime_video: str = Field(
        default="video/mp4,video/quicktime",
        alias="ASSET_ALLOWED_MIME_VIDEO",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
