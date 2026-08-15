"""Poll the hosted queue and process jobs with the local analyzer."""

from __future__ import annotations

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .local_analyzer import (
    SSL_CONTEXT,
    AnalysisError,
    ApartmentAnalyzer,
    JsonCache,
    NominatimGeocoder,
    OllamaModel,
    OsrmFootRouter,
)

LOGGER = logging.getLogger("apartment_search.analysis_worker")


class HostedQueueError(RuntimeError):
    """Raised when the hosted analysis queue rejects a request."""


class HostedAnalysisQueue:
    def __init__(self, site_url: str, secret: str, worker_id: str | None = None) -> None:
        self.site_url = site_url.rstrip("/")
        self.secret = secret
        self.worker_id = worker_id or f"{socket.gethostname()}-ollama"

    def claim(self) -> dict[str, Any] | None:
        status, payload = self._post(
            "/api/analysis/claim",
            {"worker_id": self.worker_id},
            allow_empty=True,
        )
        if status == 204:
            return None
        job = payload.get("job") if isinstance(payload, dict) else None
        if not isinstance(job, dict):
            raise HostedQueueError("Claim response did not contain a job")
        return job

    def complete(self, job: dict[str, Any], result: dict[str, Any]) -> None:
        self._post(
            "/api/analysis/results",
            {
                "id": job["id"],
                "claim_id": job["claim_id"],
                "result": result,
            },
        )

    def fail(self, job: dict[str, Any], error: str) -> None:
        self._post(
            "/api/analysis/results",
            {
                "id": job["id"],
                "claim_id": job["claim_id"],
                "error": error[:2000],
            },
        )

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        allow_empty: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(
            f"{self.site_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.secret}",
                "Content-Type": "application/json",
                "User-Agent": "ApartmentSearchLocalAnalyzer/0.2",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=45,
                context=SSL_CONTEXT,
            ) as response:
                body = response.read()
                if not body and allow_empty:
                    return response.status, {}
                parsed = json.loads(body.decode("utf-8")) if body else {}
                return response.status, parsed
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise HostedQueueError(
                f"Hosted queue returned HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise HostedQueueError(f"Hosted queue request failed: {exc}") from exc


class AnalysisWorker:
    def __init__(self, queue: HostedAnalysisQueue, analyzer: ApartmentAnalyzer) -> None:
        self.queue = queue
        self.analyzer = analyzer

    def run_once(self) -> bool:
        job = self.queue.claim()
        if job is None:
            return False
        LOGGER.info("Analyzing %s", job.get("post_url") or job.get("id"))
        try:
            result = self.analyzer.analyze(job)
            self.queue.complete(job, result)
            LOGGER.info(
                "Completed %s as %s (%s)",
                job.get("id"),
                result["category"],
                result["score"],
            )
        except Exception as exc:
            LOGGER.exception("Analysis failed for %s", job.get("id"))
            try:
                self.queue.fail(job, f"{type(exc).__name__}: {exc}")
            except HostedQueueError:
                LOGGER.exception("Could not return the failure to the hosted queue")
            if isinstance(exc, (AnalysisError, HostedQueueError)):
                return True
            raise
        return True

    def run_forever(self, poll_seconds: int = 30) -> None:
        LOGGER.info("Local apartment analyzer started")
        while True:
            try:
                processed = self.run_once()
                if not processed:
                    time.sleep(poll_seconds)
            except HostedQueueError:
                LOGGER.exception("Hosted queue is unavailable")
                time.sleep(poll_seconds)


def build_worker(
    site_url: str,
    secret: str,
    model_name: str,
    ollama_url: str,
    cache_path: Path,
) -> tuple[AnalysisWorker, JsonCache]:
    cache = JsonCache(cache_path)
    analyzer = ApartmentAnalyzer(
        model=OllamaModel(model=model_name, base_url=ollama_url),
        geocoder=NominatimGeocoder(cache),
        router=OsrmFootRouter(cache),
    )
    return AnalysisWorker(HostedAnalysisQueue(site_url, secret), analyzer), cache
