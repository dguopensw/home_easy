"""In-memory store for scraped listing data used by follow-up processing."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from threading import Lock
from time import time
import uuid
from typing import Any


@dataclass
class ScrapeRecord:
    scrape_id: str
    data: dict[str, Any]
    created_at: float = field(default_factory=time)


class ScrapeStore:
    def __init__(self) -> None:
        self._records: dict[str, ScrapeRecord] = {}
        self._lock = Lock()

    @property
    def ttl_seconds(self) -> int:
        return int(os.getenv("SCRAPE_STORE_TTL_SECONDS", "1800"))

    def create(self, data: dict[str, Any]) -> str:
        self.cleanup()
        scrape_id = f"scrape_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._records[scrape_id] = ScrapeRecord(scrape_id=scrape_id, data=data)
        return scrape_id

    def get(self, scrape_id: str) -> dict[str, Any] | None:
        self.cleanup()
        with self._lock:
            record = self._records.get(scrape_id)
            if record is None:
                return None
            if time() - record.created_at > self.ttl_seconds:
                self._records.pop(scrape_id, None)
                return None
            return dict(record.data)

    def cleanup(self) -> None:
        expires_before = time() - self.ttl_seconds
        with self._lock:
            expired_ids = [
                scrape_id
                for scrape_id, record in self._records.items()
                if record.created_at < expires_before
            ]
            for scrape_id in expired_ids:
                self._records.pop(scrape_id, None)


scrape_store = ScrapeStore()
