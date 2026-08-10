from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    autoheal_host: str = "0.0.0.0"
    autoheal_port: int = 8000

    jenkins_url: str
    jenkins_username: str
    jenkins_api_token: str

    webhook_secret: str

    class Config:
        env_file = ".env"


settings = Settings()