"""
Exceptions used across the backend and the structured JSON error format.

Every error response has the same shape:
    {"error": {"code": "PROMETHEUS_UNAVAILABLE", "message": "...", "details": {...}}}
"""
from typing import Any


class PlatformError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class KubernetesUnavailable(PlatformError):
    status_code = 503
    code = "KUBERNETES_UNAVAILABLE"


class PrometheusUnavailable(PlatformError):
    """Prometheus could not be reached (connection refused, DNS, timeout)."""
    status_code = 503
    code = "PROMETHEUS_UNAVAILABLE"


class PrometheusQueryError(PlatformError):
    """Prometheus answered, but the query failed or the answer was malformed."""
    status_code = 502
    code = "PROMETHEUS_QUERY_ERROR"


class ServiceNotFound(PlatformError):
    status_code = 404
    code = "SERVICE_NOT_FOUND"


class LLMNotConfigured(PlatformError):
    status_code = 503
    code = "LLM_NOT_CONFIGURED"


class LLMError(PlatformError):
    status_code = 502
    code = "LLM_API_ERROR"
