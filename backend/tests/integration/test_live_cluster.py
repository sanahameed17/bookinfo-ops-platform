"""
LIVE integration tests against YOUR cluster and Prometheus (read-only).

They are skipped unless LIVE_TESTS=1, because they need:
  * the docker-desktop Kubernetes cluster running with Bookinfo in namespace bookinfo
  * kubectl port-forward -n monitoring svc/prometheus-operator-kube-p-prometheus 9091:9090

PowerShell:
  $env:LIVE_TESTS = "1"; python -m pytest tests/integration -v
"""
import os

import pytest

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.getenv("LIVE_TESTS") != "1", reason="set LIVE_TESTS=1 to run live tests")]


@pytest.fixture(scope="module")
def platform():
    from app.deps import get_platform
    return get_platform()


def test_kubernetes_connectivity(platform):
    v = platform.k8s.version()
    assert v.get("gitVersion", "").startswith("v")


def test_service_discovery(platform):
    names = {c["name"] for c in platform.list_services()["services"]}
    assert {"productpage", "details", "ratings", "reviews"} <= names


def test_deployment_discovery_reviews_versions(platform):
    w = platform.service_workloads("reviews")
    assert {d["version"] for d in w["deployments"]} >= {"v1", "v2", "v3"}


def test_pod_discovery(platform):
    pods = platform.pods()["pods"]
    assert len(pods) >= 6 and all(p["deployment"] for p in pods if p.get("service"))


def test_prometheus_connectivity(platform):
    assert platform.metrics.status()["available"], platform.metrics.status()["error"]


def test_cpu_and_memory_metrics_live(platform):
    m = platform.metrics.current_by_pod()
    assert m["available"] and m["cpu"] and m["memory"]
    assert all(v is None or v >= 0 for v in m["cpu"].values())


def test_restart_metrics_live(platform):
    assert platform.metrics.restarts()["available"]


def test_service_detail_live(platform):
    d = platform.service_detail("productpage")
    assert d["service"]["cluster_ip"] and d["pods"]
