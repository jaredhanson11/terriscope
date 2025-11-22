"""Application configuration."""

from typing import Literal, cast

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings, env_prefix="DB_"):
    """Database settings."""

    name: str = Field(default=...)
    user: str = Field(default=...)
    host: str = Field(default=...)
    port: int = 5432
    password: str = Field(default=...)
    echo: bool = False

    @property
    def db_url(self) -> str:
        """Database string based on inputs."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class JWTSettings(BaseSettings, env_prefix="JWT_"):
    """JWT authentication settings."""

    secret: str = Field(default=...)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    cookie_secure: bool = False
    cookie_domain: str | None = None


class CORSSettings(BaseSettings, env_prefix="CORS_"):
    """CORS settings."""

    allowed_origins: list[HttpUrl] = Field(default_factory=lambda: cast(list[HttpUrl], []))


class AppSettings(BaseSettings):
    """Application settings."""

    debug: bool = False
    database: DatabaseSettings = DatabaseSettings()
    jwt: JWTSettings = JWTSettings()
    cors: CORSSettings = CORSSettings()
    log_level: Literal["CRITICAL", "FATAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"] = "INFO"


app_settings = AppSettings()
