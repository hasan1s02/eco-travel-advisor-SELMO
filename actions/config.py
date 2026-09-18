"""Runtime configuration for the Eco-Travel Advisor action server.

Every external dependency is optional. If the corresponding environment
variable is absent the action server falls back to the curated offline
datasets in ``actions/data`` and flags the response as demonstration data, so
the assistant never silently presents mock figures as live ones.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Loading a .env file is a developer convenience only; in Docker the variables
# arrive through the environment and python-dotenv may not be installed.
try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # pragma: no cover
    pass


DATA_DIR = Path(__file__).resolve().parent / "data"

# Non-functional requirement from section 2 of the brief: critical
# interactions respond in under three seconds. Each outbound call therefore
# gets a hard timeout well inside that budget, and every client degrades to
# offline data rather than blocking the dialogue.
HTTP_TIMEOUT_SECONDS = float(os.getenv("ECO_HTTP_TIMEOUT", "2.0"))

# Cache TTL for outbound lookups. Emission factors and geocodes change on a
# scale of months, so caching them keeps us inside both the latency budget and
# the free-tier request quotas listed in the brief.
CACHE_TTL_SECONDS = int(os.getenv("ECO_CACHE_TTL", str(60 * 60 * 24)))


@dataclass
class Settings:
    """Resolved configuration, read once at import time.

    Deliberately mutable rather than frozen: the test suite overrides single
    fields to exercise the live-API and failure paths without setting real
    environment variables, and a frozen dataclass makes that impossible.
    """

    climatiq_api_key: str | None = field(default_factory=lambda: os.getenv("CLIMATIQ_API_KEY") or None)
    climatiq_data_version: str = field(default_factory=lambda: os.getenv("CLIMATIQ_DATA_VERSION", "^19"))

    amadeus_client_id: str | None = field(default_factory=lambda: os.getenv("AMADEUS_CLIENT_ID") or None)
    amadeus_client_secret: str | None = field(default_factory=lambda: os.getenv("AMADEUS_CLIENT_SECRET") or None)
    amadeus_base_url: str = field(default_factory=lambda: os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com"))

    opencage_api_key: str | None = field(default_factory=lambda: os.getenv("OPENCAGE_API_KEY") or None)
    openroute_api_key: str | None = field(default_factory=lambda: os.getenv("OPENROUTESERVICE_API_KEY") or None)

    # Where a real deployment would post the escalation payload. Unset in the
    # submission build, in which case handovers are written to a local queue.
    handover_webhook_url: str | None = field(default_factory=lambda: os.getenv("HANDOVER_WEBHOOK_URL") or None)
    handover_queue_path: Path = field(
        default_factory=lambda: Path(os.getenv("HANDOVER_QUEUE_PATH", "/tmp/eco_handovers.jsonl"))
    )

    # Set ECO_FORCE_OFFLINE=1 to exercise the fallback paths even when keys are
    # present. The test suite relies on this.
    force_offline: bool = field(default_factory=lambda: os.getenv("ECO_FORCE_OFFLINE", "0") == "1")

    @property
    def climatiq_enabled(self) -> bool:
        return bool(self.climatiq_api_key) and not self.force_offline

    @property
    def amadeus_enabled(self) -> bool:
        return bool(self.amadeus_client_id and self.amadeus_client_secret) and not self.force_offline

    @property
    def opencage_enabled(self) -> bool:
        return bool(self.opencage_api_key) and not self.force_offline

    @property
    def openroute_enabled(self) -> bool:
        return bool(self.openroute_api_key) and not self.force_offline


SETTINGS = Settings()


def describe_mode() -> str:
    """Return 'live', 'hybrid' or 'demo' for the transparency disclosures."""
    flags = [
        SETTINGS.climatiq_enabled,
        SETTINGS.amadeus_enabled,
        SETTINGS.opencage_enabled,
    ]
    if all(flags):
        return "live"
    if any(flags):
        return "hybrid"
    return "demo"
