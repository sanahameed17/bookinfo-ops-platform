"""
Thin, read-only client for the Prometheus HTTP API (/api/v1/query, /api/v1/query_range,
/api/v1/status/buildinfo). Reused idea from Lab 2 (bookinfo_monitor_v2.py / prom_range_export.py):
same PromQL family, same proxy bypass - but with timeouts, typed errors and no zero-filling.
"""
import logging
import time

import httpx

from app.clients.prom_results import parse_matrix, parse_vector
from app.errors import PrometheusQueryError, PrometheusUnavailable

log = logging.getLogger(__name__)


class PrometheusClient:
    def __init__(self, base_url: str, timeout: float = 8.0, use_system_proxy: bool = False,
                 transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout,
                                    trust_env=use_system_proxy, transport=transport)

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict | None = None) -> dict:
        started = time.perf_counter()
        try:
            resp = self._client.get(path, params=params)
        except httpx.TimeoutException as e:
            raise PrometheusUnavailable(f"Prometheus at {self.base_url} timed out",
                                        {"url": self.base_url, "reason": type(e).__name__}) from e
        except httpx.HTTPError as e:
            raise PrometheusUnavailable(
                f"Cannot reach Prometheus at {self.base_url}. Is the port-forward running?",
                {"url": self.base_url, "reason": f"{type(e).__name__}: {e}"}) from e
        finally:
            log.debug("prometheus GET %s %.0f ms", path, (time.perf_counter() - started) * 1000)

        if resp.status_code >= 500 and resp.status_code != 503:
            raise PrometheusQueryError(f"Prometheus returned HTTP {resp.status_code}",
                                       {"body": resp.text[:300]})
        if resp.status_code == 503:
            raise PrometheusUnavailable("Prometheus is not ready (HTTP 503)", {"url": self.base_url})
        try:
            return resp.json()
        except ValueError as e:
            raise PrometheusQueryError("Prometheus returned invalid JSON",
                                       {"status": resp.status_code, "body": resp.text[:300]}) from e

    # ---------------------------------------------------------------------------------------
    def buildinfo(self) -> dict:
        payload = self._get("/api/v1/status/buildinfo")
        if payload.get("status") != "success":
            raise PrometheusQueryError("buildinfo query failed", {"payload": payload})
        return payload.get("data", {})

    def query(self, promql: str) -> list[dict]:
        return parse_vector(self._get("/api/v1/query", {"query": promql}))

    def query_range(self, promql: str, start: float, end: float, step: int) -> list[dict]:
        return parse_matrix(self._get("/api/v1/query_range",
                                      {"query": promql, "start": start, "end": end, "step": step}))
