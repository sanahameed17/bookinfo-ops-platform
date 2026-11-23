"""Dependency injection: one shared PlatformService per process (tests replace it)."""
from functools import lru_cache

from app.config import get_settings


@lru_cache
def get_platform():
    from app.clients.jaeger_client import JaegerClient
    from app.clients.k8s_client import K8sClient
    from app.clients.prometheus_client import PrometheusClient
    from app.services.platform import PlatformService

    s = get_settings()
    k8s = K8sClient(context=s.k8s_context, in_cluster=s.k8s_in_cluster,
                    timeout=s.k8s_request_timeout_seconds, cache_seconds=s.k8s_cache_seconds)
    prom = PrometheusClient(s.prometheus_url, timeout=s.prometheus_timeout_seconds,
                            use_system_proxy=s.prometheus_use_system_proxy)
    jaeger = JaegerClient(s.jaeger_url, timeout=s.jaeger_timeout_seconds,
                          use_system_proxy=s.prometheus_use_system_proxy) if s.jaeger_url else None
    return PlatformService(s, k8s, prom, jaeger)


@lru_cache
def get_agent_runner():
    from app.agent.runner import AgentRunner
    return AgentRunner(get_settings(), get_platform())
