
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
    ai_timeout_seconds: float = 180.0
    ai_failure_context_lines: int = 35
    ai_stage_max_chars: int = 8000
    ai_max_failure_candidates: int = 80

    # OpenTelemetry
    otel_endpoint: str = (
        "http://otel-collector:4318"
    )
    otel_enabled: bool = True

    # Alertmanager
    # Required so the Alertmanager webhook cannot be deployed without auth.
    alertmanager_secret: str
    slack_webhook_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()

