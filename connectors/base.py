"""
Connector interface.

Every data source in AI IT Operations — synthetic CSV today, a real
Zoho/Sophos/FortiGate API tomorrow — implements this same shape. The
rest of the pipeline (engines, AI, reporting) only ever talks to this
interface, never to a vendor's actual API shape. That's what lets a
new customer's toolset be supported by adding one connector file,
without touching anything else.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ConnectorHealth:
    connector_name: str
    healthy: bool
    last_run_at: datetime
    records_fetched: int
    error: str | None = None


class Connector(ABC):
    """Base class for every data source connector."""

    name: str = "base"

    @abstractmethod
    def authenticate(self) -> None:
        """Set up credentials/session. No-op for synthetic connectors."""
        raise NotImplementedError

    @abstractmethod
    def fetch(self, since: datetime | None = None) -> list[dict]:
        """Return raw records from the source, optionally since a timestamp."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw_records: list[dict]) -> list[dict]:
        """Map source-specific fields onto the common internal data model."""
        raise NotImplementedError

    def health_check(self, records_fetched: int, error: str | None = None) -> ConnectorHealth:
        """
        Every connector reports its own health. Never log secrets or
        payload contents here — only counts, timestamps, and error codes.
        """
        return ConnectorHealth(
            connector_name=self.name,
            healthy=error is None,
            last_run_at=datetime.now(timezone.utc),
            records_fetched=records_fetched,
            error=error,
        )
