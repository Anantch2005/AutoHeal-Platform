from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    autoheal_host: str = "0.0.0.0"
    autoheal_port: int = 8000

    jenkins_url: str
    jenkins_username: str
    jenkins_api_token: str

    webhook_secret: str

    database_url: str = (
        "postgresql+psycopg2://"
        "autoheal:autoheal@postgres:5432/autoheal"
    )

    # AI
    ai_enabled: bool = False
    openai_api_key: str | None = None
    ai_model: str = "gpt-5-mini"
    ai_max_log_chars: int = 12000

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()