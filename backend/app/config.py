"""
Application settings, read from environment variables (and from a .env file in development).

Every value has a safe default for the local Windows set-up found in Phase 1:
  * Kubernetes context  docker-desktop   (Docker Desktop built-in Kubernetes, kind provisioner)
  * Prometheus          http://127.0.0.1:9091  (kubectl port-forward to
                        svc/prometheus-operator-kube-p-prometheus in namespace monitoring)
  * Jaeger              http://127.0.0.1:16686/jaeger  (kubectl port-forward to svc/tracing)

Secrets (the LLM API key) are only read here and are never returned by any API endpoint.
"""
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8",
                                      extra="ignore")

    app_name: str = "Bookinfo Observability & AI Operations Platform"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"

    # --- Kubernetes -------------------------------------------------------------------------
    k8s_namespace: str = "bookinfo"
    k8s_context: str = Field(default="docker-desktop",
                             description="kubeconfig context; empty = current context")
    k8s_in_cluster: bool = False
    k8s_request_timeout_seconds: float = 10.0
    k8s_cache_seconds: float = 5.0

    # --- Prometheus -------------------------------------------------------------------------
    prometheus_url: str = "http://127.0.0.1:9091"
    prometheus_timeout_seconds: float = 8.0
    prometheus_rate_window: str = "2m"
    # The Windows system proxy (Clash) intercepted localhost requests in Lab 2.
    # False = ignore HTTP(S)_PROXY / system proxy for Prometheus and Jaeger requests.
    prometheus_use_system_proxy: bool = False

    # --- Jaeger (optional, only for service dependencies) ------------------------------------
    jaeger_url: str = "http://127.0.0.1:16686/jaeger"
    jaeger_timeout_seconds: float = 5.0

    # --- Deterministic anomaly thresholds ----------------------------------------------------
    cpu_threshold_cores: float = 0.1
    memory_threshold_mib: float = 400.0
    restart_threshold: int = Field(default=0, description="restarts above this are reported "
                                                          "as a warning (not an anomaly)")

    # --- LLM for the AI OpsAgent (OpenAI-compatible: DeepSeek, Zhipu GLM, OpenAI, ...) ------
    llm_provider: str = "deepseek"
    llm_api_key: str = Field(default="", repr=False)
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 60.0
    llm_max_iterations: int = 8
    # Lab 3 used OPENAI_API_KEY / OPENAI_BASE_URL / MODEL_NAME; they are accepted as fallbacks.
    openai_api_key: str = Field(default="", repr=False)
    openai_base_url: str = ""
    model_name: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_llm_api_key(self) -> str:
        return self.llm_api_key or self.openai_api_key

    @property
    def effective_llm_base_url(self) -> str:
        return self.openai_base_url if (not self.llm_api_key and self.openai_base_url) else self.llm_base_url

    @property
    def effective_llm_model(self) -> str:
        return self.model_name if (not self.llm_api_key and self.model_name) else self.llm_model

    @property
    def llm_configured(self) -> bool:
        return bool(self.effective_llm_api_key)

    def public_view(self) -> dict:
        """Settings that are safe to show in the frontend (no secrets)."""
        base = urlparse(self.effective_llm_base_url)
        return {
            "namespace": self.k8s_namespace,
            "kubernetes_context": self.k8s_context or "(current context)",
            "kubernetes_in_cluster": self.k8s_in_cluster,
            "prometheus_url": self.prometheus_url,
            "prometheus_timeout_seconds": self.prometheus_timeout_seconds,
            "prometheus_rate_window": self.prometheus_rate_window,
            "jaeger_url": self.jaeger_url,
            "cpu_threshold_cores": self.cpu_threshold_cores,
            "memory_threshold_mib": self.memory_threshold_mib,
            "llm_provider": self.llm_provider,
            "llm_model": self.effective_llm_model,
            "llm_base_url_host": base.netloc or self.effective_llm_base_url,
            "llm_configured": self.llm_configured,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
