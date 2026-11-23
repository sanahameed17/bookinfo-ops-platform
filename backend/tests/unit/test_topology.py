"""Istio routing extraction and dependency edges (never guessed from names)."""
from app.services import topology
from app.services.platform import PlatformService
from tests.fakes import FakeK8s, FakeProm, settings

ISTIO = {"installed": True, "items": [
    {"kind": "VirtualService", "metadata": {"name": "reviews", "namespace": "bookinfo"},
     "spec": {"hosts": ["reviews"], "http": [{"route": [
         {"destination": {"host": "reviews", "subset": "v1"}, "weight": 20},
         {"destination": {"host": "reviews", "subset": "v2"}, "weight": 40},
         {"destination": {"host": "reviews", "subset": "v3"}, "weight": 40}]}]}},
    {"kind": "VirtualService", "metadata": {"name": "bookinfo", "namespace": "default"},
     "spec": {"hosts": ["*"], "gateways": ["bookinfo-gateway"], "http": [{"route": [
         {"destination": {"host": "productpage.bookinfo.svc.cluster.local", "port": {"number": 9080}}}]}]}},
    {"kind": "DestinationRule", "metadata": {"name": "reviews", "namespace": "bookinfo"},
     "spec": {"host": "reviews", "subsets": [{"name": "v1", "labels": {"version": "v1"}},
                                             {"name": "v2", "labels": {"version": "v2"}}]}},
    {"kind": "Gateway", "metadata": {"name": "bookinfo-gateway", "namespace": "default"},
     "spec": {"servers": [{"port": {"number": 8080}}]}},
]}


def test_reviews_weights_and_subsets():
    r = topology.istio_for_service(ISTIO, "reviews", "bookinfo")
    assert [x["weight"] for x in r["virtual_services"][0]["routes"]] == [20, 40, 40]
    assert [s["name"] for s in r["destination_rules"][0]["subsets"]] == ["v1", "v2"]


def test_gateway_virtualservice_in_default_namespace_is_found():
    r = topology.istio_for_service(ISTIO, "productpage", "bookinfo")
    assert r["virtual_services"][0]["namespace"] == "default"
    assert r["gateways"][0]["name"] == "bookinfo-gateway"


def test_istio_not_installed():
    assert topology.istio_for_service({"installed": False}, "reviews", "bookinfo")["installed"] is False


def test_edges_from_istio_metrics():
    class Prom(FakeProm):
        def query(self, q):
            if "istio_requests_total" in q:
                return [{"labels": {"source_workload": "productpage-v1", "destination_workload": "reviews-v2",
                                    "destination_service_name": "reviews"}, "value": 1.5}]
            return super().query(q)
    p = PlatformService(settings(), FakeK8s(istio=ISTIO), Prom())
    d = p.service_dependencies("productpage")
    assert d["available"] and d["calls"] == ["reviews"] and "istio" in d["source"]
    assert p.service_detail("reviews")["istio"]["virtual_services"][0]["name"] == "reviews"


def test_no_dependency_data_is_explained():
    d = PlatformService(settings(), FakeK8s(), FakeProm()).service_dependencies("details")
    assert d["available"] is False and d["calls"] == [] and "unavailable" in d["note"]
