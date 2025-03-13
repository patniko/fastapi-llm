import os
from functools import lru_cache

from loguru import logger
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

APP_ENV = os.environ.get("FASTAPI_ENV", "prod")
logger.info(f"Running with FASTAPI_ENV: {APP_ENV}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.base", f".env.{APP_ENV}"), extra="ignore"
    )
    auth_secret_key: str | None = None
    auth_algorithm: str | None = None
    auth_access_token_expire_minutes: int | None = None

    sql_host: str
    sql_port: str
    sql_user: str
    sql_password: str
    sql_database: str

    redis_host: str
    redis_port: str
    redis_password: str | None = None
    redis_db: int = 0

    kafka_host: str | None = None
    kafka_port: str | None = None

    def kafka_server(self):
        return self.kafka_host + ":" + self.kafka_port

    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    cloudflare_image_upload_url: str | None = None

    twilio_client_id: str | None = None
    twilio_client_key: str | None = None
    twilio_verify: str | None = None

    apns_key_id: str | None = None
    apns_team_id: str | None = None
    apns_bundle_id: str | None = None
    is_production: bool = False

    # Anthropic settings
    anthropic_api_key: str | None = None

    # Google Maps settings
    google_maps_api_key: str | None = None

    # Google OAuth settings
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_pubsub_topic: str | None = None

    app_env: str = APP_ENV


@lru_cache()
def get_settings():
    return Settings()


def get_sqlConnectionString():
    settings = get_settings()
    connection = (
        "postgresql://"
        + settings.sql_user
        + ":"
        + settings.sql_password
        + "@"
        + settings.sql_host
        + ":"
        + settings.sql_port
        + "/"
        + settings.sql_database
    )
    logger.debug(f"Connection string: {connection}")
    return connection
