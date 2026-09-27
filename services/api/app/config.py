from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "My Career AI"
    environment: str = "local"  # local | staging | production
    cors_origins: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg://mycareer:mycareer@localhost:5432/mycareer"

    # Auth. "dev" also enables the passwordless /auth/dev-login endpoint for local work;
    # use AUTH_MODE=supabase in staging/prod. Supabase tokens are verified either with the
    # project's signing keys (SUPABASE_URL -> JWKS, for ES256/RS256 tokens) or with its legacy
    # JWT secret (JWT_SECRET, HS256). Dev-login tokens are always HS256 with JWT_SECRET.
    auth_mode: str = "dev"  # dev | supabase
    supabase_url: str = ""
    jwt_secret: str = "dev-only-jwt-secret-change-me-in-prod-0123456789"
    jwt_audience: str = "authenticated"

    # Shared secret the voice agent uses to call /internal/* endpoints.
    internal_api_key: str = "dev-internal-key"

    # LLM. The fast model runs the live interview turns (in the agent); the smart
    # model does the one-off heavy work here: parsing, planning, evaluation.
    anthropic_api_key: str = ""
    llm_model_smart: str = "claude-opus-5"
    llm_model_fast: str = "claude-haiku-4-5"

    # LiveKit
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"
    livekit_agent_name: str = "mycareer-interviewer"

    # Storage for resumes: "local" (dev) or "s3" (Cloudflare R2 / Supabase Storage / S3).
    storage_backend: str = "local"
    storage_local_dir: str = "./data/uploads"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "auto"

    max_resume_mb: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
