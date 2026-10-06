from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    public_base_url: str  # https URL Shopify redirects back to

    aws_region: str = "us-east-1"
    kms_key_id: str

    shopify_client_id: str
    shopify_client_secret: str
    shopify_api_version: str = "2026-10"
    shopify_scopes: str = (
        "read_products,write_products,write_translations,read_locales,read_discounts,"
        "write_discounts,write_content,write_files,read_inventory,read_reports"
    )

    connect_state_secret: str  # shared with the Worker, which signs connect links
    read_capability_secret: str  # shared with the Worker, which issues job-scoped read tokens
    gateway_read_key: str  # Worker and CRE reads
    gateway_write_key: str  # CRE only (Vault DON secret)

    worker_hook_url: str | None = None  # POST target when a store connects
    worker_hook_secret: str | None = None

    port: int = 8080


@lru_cache
def settings() -> Settings:
    return Settings()
