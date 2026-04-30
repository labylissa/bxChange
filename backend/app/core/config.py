import json

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    encryption_key: str
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]
    super_admin_email: str = ""
    super_admin_password: str = ""
    # SSO / SP settings
    sp_entity_id: str = "https://app.bxchange.io"
    sp_acs_url: str = "https://app.bxchange.io/api/v1/sso/acs"
    sp_certificate: str = ""   # PEM, no headers, single line
    sp_private_key: str = ""   # PEM, no headers, single line

    model_config = {"env_file": ".env"}

    def model_post_init(self, __context) -> None:
        if isinstance(self.cors_origins, str):
            object.__setattr__(self, "cors_origins", json.loads(self.cors_origins))


settings = Settings()
