"""
Pure functions that turn Prometheus HTTP API answers into Python values.

Rules (from the project requirements):
  * an empty result stays empty - it is NEVER turned into 0;
  * NaN / +Inf / -Inf samples become None ("no usable value"), not 0;
  * timestamps are returned as UTC ISO 8601 strings.
"""
import math
from datetime import datetime, timezone
from typing import Any

from app.errors import PrometheusQueryError


def to_iso(ts: float) -> str:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def to_float(raw: Any) -> float | None:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _check(payload: Any, expected: tuple[str, ...]) -> list:
    if not isinstance(payload, dict):
        raise PrometheusQueryError("Prometheus returned a non-JSON-object answer")
    if payload.get("status") != "success":
        raise PrometheusQueryError(
            f"Prometheus query failed: {payload.get('errorType', 'error')}: {payload.get('error', '')}",
            {"errorType": payload.get("errorType"), "error": payload.get("error")},
        )
    data = payload.get("data") or {}
    if data.get("resultType") not in expected:
        raise PrometheusQueryError(f"Unexpected Prometheus resultType {data.get('resultType')!r}")
    result = data.get("result")
    if not isinstance(result, list):
        raise PrometheusQueryError("Prometheus answer has no result list")
    return result


def parse_vector(payload: Any) -> list[dict]:
    """Instant query -> [{"labels": {...}, "value": float|None, "timestamp": iso}]"""
    out = []
    for series in _check(payload, ("vector",)):
        ts, raw = series.get("value", [None, None])
        out.append({
            "labels": series.get("metric", {}),
            "value": to_float(raw),
            "timestamp": to_iso(ts) if ts is not None else None,
        })
    return out


def parse_matrix(payload: Any) -> list[dict]:
    """Range query -> [{"labels": {...}, "points": [{"t": iso, "v": float|None}, ...]}]"""
    out = []
    for series in _check(payload, ("matrix",)):
        points = [{"t": to_iso(ts), "v": to_float(v)} for ts, v in series.get("values", [])]
        out.append({"labels": series.get("metric", {}), "points": points})
    return out


def by_label(samples: list[dict], label: str) -> dict[str, float | None]:
    """Index instant-query samples by one label. Pods that are not in the result are simply
    absent from the dict, so callers can tell 'no data' (missing key) from a real value."""
    return {s["labels"].get(label, "?"): s["value"] for s in samples}
