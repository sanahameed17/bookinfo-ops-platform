"""Service / Deployment / ReplicaSet / Pod discovery on a fake Bookinfo namespace."""
from app.services import discovery
from tests.fakes import bookinfo_snapshot


def inv(**kw):
    return {v["service"]["name"]: v for v in discovery.build_inventory(bookinfo_snapshot(**kw))}


def test_four_logical_services_not_six():
    services = inv()
    assert sorted(services) == ["details", "productpage", "ratings", "reviews"]


def test_reviews_has_three_versions_and_deployments():
    reviews = inv()["reviews"]
    assert reviews["versions"] == ["v1", "v2", "v3"]
    assert [d["name"] for d in reviews["deployments"]] == ["reviews-v1", "reviews-v2", "reviews-v3"]
    assert len(reviews["pods"]) == 3
    assert {p["deployment"] for p in reviews["pods"]} == {"reviews-v1", "reviews-v2", "reviews-v3"}


def test_pod_links_through_replicaset_to_deployment():
    pp = inv()["productpage"]
    p = pp["pods"][0]
    assert p["replicaset"] == "productpage-v1-544855df4c"
    assert p["deployment"] == "productpage-v1"
    assert pp["deployments"][0]["replicasets"][0]["name"] == "productpage-v1-544855df4c"


def test_service_overview_fields():
    svc = inv()["details"]["service"]
    assert svc["type"] == "ClusterIP" and svc["selector"] == {"app": "details"}
    assert svc["ports"][0]["port"] == 9080 and svc["cluster_ip"]


def test_containers_images_probes_and_resources():
    p = inv()["ratings"]["pods"][0]
    names = [c["name"] for c in p["containers"]]
    assert names == ["ratings", "istio-proxy"]
    sidecar = p["containers"][1]
    assert sidecar["is_sidecar"] and sidecar["readiness_probe"]["configured"]
    assert sidecar["requests"] == {"cpu": "10m", "memory": "40Mi"}
    assert p["containers"][0]["readiness_probe"] == {"configured": False}


def test_healthy_namespace():
    assert all(v["health"] == "Healthy" for v in inv().values())


def test_crashloop_marks_service_down_with_reason():
    ratings = inv(broken_ratings=True)["ratings"]
    assert ratings["health"] == "Down"
    assert "CrashLoopBackOff" in ratings["health_reason"]
    assert ratings["restart_count"] == 79


def test_restart_count_sums_all_containers():
    assert inv()["productpage"]["restart_count"] == 21


def test_service_without_selector_is_unknown():
    snap = bookinfo_snapshot()
    snap["services"][0]["spec"]["selector"] = None
    v = discovery.build_inventory(snap)[0]
    assert v["health"] == "Unknown" and v["pods"] == []


def test_find_missing_service_returns_none():
    assert discovery.find_service(bookinfo_snapshot(), "nope") is None


def test_parse_quantity_and_capacity():
    assert discovery.parse_quantity("250m") == 0.25
    assert discovery.parse_quantity("128Mi") == 128 * 1048576
    cap = discovery.cluster_capacity([{"status": {"allocatable": {"cpu": "4", "memory": "8Gi"},
                                                  "conditions": [{"type": "Ready", "status": "True"}]}}])
    assert cap == {"nodes": 1, "ready_nodes": 1, "allocatable_cpu_cores": 4.0, "allocatable_memory_mib": 8192.0}


def test_events_filtered_and_sorted():
    evs = [{"type": "Warning", "reason": "BackOff", "message": "x", "involvedObject": {"kind": "Pod", "name": "a"},
            "lastTimestamp": "2026-11-23T10:00:00Z"},
           {"type": "Normal", "reason": "Pulled", "message": "y", "involvedObject": {"kind": "Pod", "name": "b"},
            "lastTimestamp": "2026-11-23T11:00:00Z"}]
    assert [e["object_name"] for e in discovery.events_for(evs, set())] == ["b", "a"]
    assert [e["object_name"] for e in discovery.events_for(evs, {"a"})] == ["a"]
