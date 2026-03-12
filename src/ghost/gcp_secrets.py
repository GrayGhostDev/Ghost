"""
GCP Secret Manager Integration

Fetches secrets from Google Cloud Secret Manager with in-memory caching.
Gracefully degrades when GCP libraries are not installed or credentials
are unavailable — existing env-var and .env workflows are unaffected.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    from google.cloud import secretmanager  # type: ignore[import-untyped]

    _GCP_AVAILABLE = True
except ImportError:
    _GCP_AVAILABLE = False

# Maps GCP secret names → (config_section, config_field) for automatic overlay
SECRET_MAP: Dict[str, tuple] = {
    "jwt-secret": ("auth", "jwt_secret"),
    "postgres-password": ("database", "password"),
    "redis-password": ("redis", "password"),
    "api-key": ("api", "api_key"),
    "sentry-dsn": ("external_apis", "sentry_dsn"),
}


class GCPSecretManager:
    """Fetch and cache secrets from GCP Secret Manager."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self._cache: Dict[str, str] = {}
        self._client: Optional[object] = None

        if not _GCP_AVAILABLE:
            logger.info(
                "google-cloud-secret-manager not installed — GCP secrets disabled"
            )
            return

        try:
            self._client = secretmanager.SecretManagerServiceClient()
            logger.info("GCP Secret Manager client initialized (project=%s)", project_id)
        except Exception as exc:
            logger.warning("Failed to create GCP Secret Manager client: %s", exc)
            self._client = None

    @property
    def available(self) -> bool:
        """True when the GCP client is ready."""
        return self._client is not None

    def get_secret(self, secret_id: str, version: str = "latest") -> Optional[str]:
        """Fetch a single secret, returning cached value if present."""
        if not self.available:
            return None

        if secret_id in self._cache:
            return self._cache[secret_id]

        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
        try:
            response = self._client.access_secret_version(request={"name": name})  # type: ignore[union-attr]
            value = response.payload.data.decode("UTF-8")
            self._cache[secret_id] = value
            logger.debug("Fetched GCP secret: %s", secret_id)
            return value
        except Exception as exc:
            logger.warning("Could not fetch GCP secret '%s': %s", secret_id, exc)
            return None

    def overlay_config(self, config: object) -> int:
        """Apply fetched secrets onto a Config dataclass.

        Returns the number of secrets successfully applied.
        """
        if not self.available:
            return 0

        applied = 0
        for secret_id, (section, field) in SECRET_MAP.items():
            value = self.get_secret(secret_id)
            if value is None:
                continue

            target = getattr(config, section, None)
            if target is None:
                continue

            current = getattr(target, field, None)
            # Only overlay if the field is empty / default
            if not current:
                setattr(target, field, value)
                applied += 1
                logger.debug("Applied GCP secret '%s' -> %s.%s", secret_id, section, field)

        if applied:
            logger.info("Applied %d secret(s) from GCP Secret Manager", applied)
        return applied
