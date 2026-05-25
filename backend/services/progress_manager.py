"""In-memory progress event store for background pipeline jobs."""
from __future__ import annotations

from dataclasses import dataclass, field
from queue import Queue
from threading import Lock
from time import time
from typing import Any
import uuid


ProgressEvent = dict[str, Any]


@dataclass
class ProgressJob:
    job_id: str
    events: list[ProgressEvent] = field(default_factory=list)
    queue: Queue[ProgressEvent] = field(default_factory=Queue)
    terminal: bool = False
    created_at: float = field(default_factory=time)
    result: dict[str, Any] | None = None
    status_code: int | None = None


class ProgressManager:
    def __init__(self) -> None:
        self._jobs: dict[str, ProgressJob] = {}
        self._lock = Lock()

    def create_job(self) -> str:
        job_id = uuid.uuid4().hex[:8]
        with self._lock:
            self._jobs[job_id] = ProgressJob(job_id=job_id)
        return job_id

    def get_job(self, job_id: str) -> ProgressJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def emit(self, job_id: str, event: ProgressEvent) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                job = ProgressJob(job_id=job_id)
                self._jobs[job_id] = job

            payload = {"job_id": job_id, **event}
            job.events.append(payload)
            if payload.get("step") in {"completed", "error"}:
                job.terminal = True
            job.queue.put(payload)

    def complete(
        self,
        job_id: str,
        result: dict[str, Any],
        status_code: int = 200,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                job = ProgressJob(job_id=job_id)
                self._jobs[job_id] = job
            job.result = result
            job.status_code = status_code


progress_manager = ProgressManager()
