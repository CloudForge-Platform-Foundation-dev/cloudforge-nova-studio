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
    # Identity Service token endpoint — used only to get Nova's own service
    # token for calling Knowledge Studio (see src/auth/service_token.py).
    token_url: str = "https://identity.cloudforge.internal/token"


auth_settings = AuthSettings()


class ServiceCredentialsSettings(BaseSettings):
    """Nova's own client credentials at the Identity Service (client_id
    `nova-studio`). There is deliberately no default secret: when it is empty
    every /query fails with 503 instead of calling Knowledge unauthenticated."""

    model_config = SettingsConfigDict(env_prefix="NOVA_")

    client_id: str = "nova-studio"
    client_secret: str = ""


service_credentials = ServiceCredentialsSettings()


def build_auth_config() -> AuthConfig:
    """Translate Nova's local settings into the shared AuthConfig."""
    return AuthConfig(
        issuer=auth_settings.jwt_issuer,
        audience=auth_settings.jwt_audience,
        jwks_url=auth_settings.jwks_url,
        jwks_cache_ttl_seconds=auth_settings.jwks_cache_ttl_seconds,
    )
