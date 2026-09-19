from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    autoheal_host: str = "0.0.0.0"
    autoheal_port: int = 8000

    jenkins_url: str
    jenkins_username: str
    jenkins_api_token: str

    webhook_secret: str

    database_url: str

    # AI / Ollama
    ai_enabled: bool = False
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"
    ai_max_log_chars: int = 12000

    # OpenTelemetry
    otel_endpoint: str = (
        "http://otel-collector:4318"
    )

    # Alertmanager
    # Required so the Alertmanager webhook cannot be deployed without auth.
    alertmanager_secret: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()