from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    secret_key: SecretStr
    tmdb_read_token: SecretStr
    debug: bool = False

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError(
                "SECRET_KEY must contain at least 32 characters"
            )
        return value

    @field_validator("tmdb_read_token")
    @classmethod
    def validate_tmdb_read_token(
        cls, value: SecretStr
    ) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError(
                "TMDB_READ_TOKEN must not be empty"
            )
        return value
