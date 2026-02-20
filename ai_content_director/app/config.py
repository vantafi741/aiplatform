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

    # Google Drive dropzone (Service Account JSON path)
    gdrive_sa_json_path: Optional[str] = Field(default=None, alias="GDRIVE_SA_JSON_PATH")
    gdrive_ready_images_folder_id: Optional[str] = Field(default=None, alias="GDRIVE_READY_IMAGES_FOLDER_ID")
    gdrive_ready_videos_folder_id: Optional[str] = Field(default=None, alias="GDRIVE_READY_VIDEOS_FOLDER_ID")
    gdrive_processed_folder_id: Optional[str] = Field(default=None, alias="GDRIVE_PROCESSED_FOLDER_ID")
    gdrive_rejected_folder_id: Optional[str] = Field(default=None, alias="GDRIVE_REJECTED_FOLDER_ID")
    local_media_dir: str = Field(default="/opt/aiplatform/media_cache", alias="LOCAL_MEDIA_DIR")
    asset_max_image_mb: int = Field(default=10, alias="ASSET_MAX_IMAGE_MB")
    asset_max_video_mb: int = Field(default=200, alias="ASSET_MAX_VIDEO_MB")

    # AI Lead System: n8n webhook khi priority=high (follow-up task)
    webhook_n8n_url: Optional[str] = Field(default=None, alias="WEBHOOK_URL")
    # Intent classify: true = gọi LLM khi rule không match (unknown); false = chỉ rule
    lead_classify_use_llm: bool = Field(default=False, alias="LEAD_CLASSIFY_USE_LLM")
    # Timeouts (seconds) for AI Lead System
    lead_classify_llm_timeout_seconds: int = Field(default=6, alias="LEAD_CLASSIFY_LLM_TIMEOUT_SECONDS")
    n8n_webhook_timeout_seconds: float = Field(default=5.0, alias="N8N_WEBHOOK_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
