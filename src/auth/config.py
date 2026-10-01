"""
Auth Settings — implements CloudForge Identity Contract v1 via
cloudforge-auth-core. Do NOT re-implement JWT verification here; this
module only supplies Nova's environment-specific values (issuer,
audience, JWKS URL) to the shared AuthConfig.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

from cloudforge_auth_core import AuthConfig


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_")

    jwt_issuer: str = "https://identity.cloudforge.internal"
    jwks_url: str = "https://identity.cloudforge.internal/.well-known/jwks.json"
    # Contract v1 §2: audience is platform-wide, not per-Studio.
    jwt_audience: str = "cloudforge-platform"
    jwks_cache_ttl_seconds: int = 3600


auth_settings = AuthSettings()


def build_auth_config() -> AuthConfig:
    """Translate Nova's local settings into the shared AuthConfig."""
    return AuthConfig(
        issuer=auth_settings.jwt_issuer,
        audience=auth_settings.jwt_audience,
        jwks_url=auth_settings.jwks_url,
        jwks_cache_ttl_seconds=auth_settings.jwks_cache_ttl_seconds,
    )
