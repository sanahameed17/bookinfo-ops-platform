"""Optional, read-only Jaeger query API client (only /api/dependencies is used)."""
import time

import httpx


class JaegerClient:
    def __init__(self, base_url: str, timeout: float = 5.0, use_system_proxy: bool = False):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout, trust_env=use_system_proxy)

    def dependencies(self, lookback_hours: int = 24) -> dict:
        end_ms = int(time.time() * 1000)
        params = {"endTs": end_ms, "lookback": lookback_hours * 3600 * 1000}
        try:
            r = self._client.get(f"{self.base_url}/api/dependencies", params=params)
            r.raise_for_status()
            data = r.json().get("data") or []
            return {"available": True, "error": None, "items": data}
        except (httpx.HTTPError, ValueError) as e:
            return {"available": False, "error": f"Jaeger not reachable at {self.base_url}: {type(e).__name__}",
                    "items": []}
