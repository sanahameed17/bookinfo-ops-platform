"""PlatformService end-to-end on fakes: overview, cards, detail, dependencies."""
import pytest

from app.errors import ServiceNotFound
from app.services.platform import PlatformService
from tests.fakes import FakeK8s, FakeProm, bookinfo_snapshot, settings

PP = "productpage-v1-544855df4c-njtnf"


def svc(prom=None, k8s=None, jaeger=None):
    return PlatformService(settings(), k8s or FakeK8s(), prom or FakeProm(), jaeger)


def test_overview_totals():
    o = svc().overview()
    t = o["totals"]
    assert t["microservices"] == 4 and t["deployments"] == 6 and t["pods"] == 6
    assert t["running_pods"] == 6 and t["unhealthy_pods"] == 0
    assert t["container_restarts"] == 21 + 5 * 3
    assert t["cpu_cores"] == pytest.approx(0.06) and t["memory_mib"] == pytest.approx(900.0)
    assert t["cpu_percent_of_cluster"] == pytest.approx(1.5)
    assert o["status"] == "normal"


def test_overview_without_prometheus_has_no_fake_numbers():
    o = svc(FakeProm(down=True)).overview()
    assert o["totals"]["cpu_cores"] is None and o["totals"]["memory_mib"] is None
    assert o["prometheus"]["available"] is False
    assert o["status"] == "prometheus_unavailable"
    assert any("Prometheus unavailable" in w for w in o["warnings"])


def test_overview_warns_about_chaos_experiments():
    chaos = {"installed": True, "items": [{"kind": "NetworkChaos", "metadata": {
        "name": "bookinfo-network-delay-rerun", "creationTimestamp": "2026-10-31T11:00:00Z"}}]}
    o = svc(k8s=FakeK8s(chaos=chaos)).overview()
    assert o["chaos_experiments"][0]["name"] == "bookinfo-network-delay-rerun"


def test_service_cards():
    cards = {c["name"]: c for c in svc().list_services()["services"]}
    r = cards["reviews"]
    assert r["version_count"] == 3 and r["pod_count"] == 3 and r["ready_replicas"] == 3
    assert r["cpu_cores"] == pytest.approx(0.03) and r["status"] == "normal"


def test_service_card_down_service():
    cards = {c["name"]: c for c in svc(k8s=FakeK8s(bookinfo_snapshot(broken_ratings=True))).list_services()["services"]}
    assert cards["ratings"]["health"] == "Down" and cards["ratings"]["status"] == "anomalous"


def test_service_detail():
    d = svc().service_detail("productpage")
    assert d["service"]["name"] == "productpage"
    assert d["pods"][0]["cpu_cores"] == 0.01
    assert d["pods"][0]["containers"][0]["cpu_cores"] == 0.01  # container-level
    assert d["diagnostics"]["crashloop_pods"] == []
    assert d["diagnostics"]["resources_configured"] is False
    assert d["dependencies"]["available"] is False  # no istio data and no jaeger -> explained
    assert "unavailable" in d["dependencies"]["note"]


def test_unknown_service_404():
    with pytest.raises(ServiceNotFound) as e:
        svc().service_detail("nope")
    assert "reviews" in e.value.details["available_services"]


def test_dependencies_from_jaeger():
    class J:
        def dependencies(self):
            return {"available": True, "error": None, "items": [
                {"parent": "productpage.bookinfo", "child": "reviews.bookinfo", "callCount": 40},
                {"parent": "reviews.bookinfo", "child": "ratings.bookinfo", "callCount": 25}]}
    d = svc(jaeger=J()).service_dependencies("reviews")
    assert d["available"] and d["calls"] == ["ratings"] and d["called_by"] == ["productpage"]


def test_history_per_service_uses_pod_regex():
    prom = FakeProm()
    h = svc(prom).service_history("reviews", "cpu", 5)
    assert len(h["series"]) == 3 and h["unit"] == "cores"
    assert 'pod=~"(reviews-v1|reviews-v2|reviews-v3)' in h["query"]


def test_health_endpoint_logic():
    h = svc(FakeProm(down=True)).health()
    assert h["kubernetes"]["ok"] is True and h["prometheus"]["available"] is False
    assert h["status"] == "degraded"
