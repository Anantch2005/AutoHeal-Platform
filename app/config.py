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

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()