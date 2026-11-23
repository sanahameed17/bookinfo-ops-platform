"""PromQL parsing, metric collection (empty / missing / unavailable) and deterministic status."""
import pytest

from app.clients.prom_results import parse_matrix, parse_vector
from app.errors import PrometheusQueryError
from app.services import status
from app.services.metrics import MetricsService, attach_metrics, pod_regex, q_cpu, q_memory, sum_or_none
from app.services.discovery import link_pods
from tests.fakes import FakeProm, bookinfo_snapshot, pod_names

PP = "productpage-v1-544855df4c-njtnf"


# ---------------------------------------------------------------- parsing
def test_parse_vector_keeps_nan_as_none_and_utc_iso():
    payload = {"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": {"pod": "a"}, "value": [1763902800, "0.5"]},
        {"metric": {"pod": "b"}, "value": [1763902800, "NaN"]}]}}
    out = parse_vector(payload)
    assert out[0]["value"] == 0.5 and out[1]["value"] is None
    assert out[0]["timestamp"].endswith("Z") and out[0]["timestamp"].startswith("2025-11-23T")


def test_parse_empty_vector_stays_empty():
    assert parse_vector({"status": "success", "data": {"resultType": "vector", "result": []}}) == []


def test_parse_error_raises():
    with pytest.raises(PrometheusQueryError):
        parse_vector({"status": "error", "errorType": "bad_data", "error": "parse error"})


def test_parse_matrix():
    payload = {"status": "success", "data": {"resultType": "matrix", "result": [
        {"metric": {"pod": "a"}, "values": [[1763902800, "1"], [1763902815, "+Inf"]]}]}}
    pts = parse_matrix(payload)[0]["points"]
    assert pts[0]["v"] == 1.0 and pts[1]["v"] is None


# ---------------------------------------------------------------- PromQL
def test_queries_use_cores_mib_and_exclude_pause_containers():
    q = q_cpu("bookinfo", "2m")
    assert 'container!="POD"' in q and 'container!=""' in q and "rate(" in q and "* 1000" not in q
    assert q_memory("bookinfo").endswith("/ 1048576")


def test_pod_regex_matches_versions_only():
    import re
    rx = pod_regex(["reviews-v1", "reviews-v3"])
    assert re.fullmatch(rx, "reviews-v1-847664ccd7-mfjkw")
    assert not re.fullmatch(rx, "reviews-v2-6dfdd6c5b9-qdbsd")
    assert pod_regex([]) is None


# ---------------------------------------------------------------- collection
def test_cpu_and_memory_metrics():
    m = MetricsService(FakeProm(cpu={PP: 0.02}, mem={PP: 310.0}), "bookinfo").current_by_pod()
    assert m["available"] and m["cpu"][PP] == 0.02 and m["memory"][PP] == 310.0


def test_missing_metric_is_none_not_zero():
    prom = FakeProm(missing={PP})
    m = MetricsService(prom, "bookinfo").current_by_pod()
    pods = attach_metrics(link_pods(bookinfo_snapshot()), m)
    pp = next(p for p in pods if p["name"] == PP)
    assert pp["cpu_cores"] is None and pp["memory_mib"] is None
    assert pp["metrics_state"] == "metrics_unavailable"


def test_empty_prometheus_result():
    m = MetricsService(FakeProm(empty=True), "bookinfo").current_by_pod()
    assert m["available"] and m["cpu"] == {} and m["memory"] == {}


def test_prometheus_failure_is_reported_not_raised():
    svc = MetricsService(FakeProm(down=True), "bookinfo")
    m = svc.current_by_pod()
    assert m["available"] is False and "Cannot reach Prometheus" in m["error"]
    assert svc.status()["available"] is False
    assert svc.restarts()["available"] is False


def test_restart_metrics():
    r = MetricsService(FakeProm(), "bookinfo").restarts()
    assert r["available"] and len(r["items"]) == 6 and r["items"][0]["restarts"] == 3


def test_history_rejects_unknown_range_and_keeps_gaps():
    svc = MetricsService(FakeProm(), "bookinfo")
    with pytest.raises(ValueError):
        svc.history("cpu", 7)
    h = svc.history("memory", 15)
    assert h["unit"] == "MiB" and h["step_seconds"] == 30
    assert h["series"][0]["points"][1]["v"] is None


def test_sum_or_none():
    assert sum_or_none([None, None]) is None
    assert sum_or_none([1.0, None, 2.0]) == 3.0


# ---------------------------------------------------------------- deterministic status
def _evaluate(prom, snap=None):
    pods = link_pods(snap or bookinfo_snapshot())
    m = MetricsService(prom, "bookinfo").current_by_pod()
    return status.evaluate(pods, m, 0.1, 400.0)


def test_status_normal():
    assert _evaluate(FakeProm())["status"] == "normal"


def test_status_cpu_anomaly_names_pod_and_metric():
    r = _evaluate(FakeProm(cpu={**{n: 0.01 for n in pod_names()}, PP: 0.35}))
    assert r["status"] == "anomalous"
    a = r["anomalies"][0]
    assert a["pod"] == PP and a["metric"] == "cpu" and a["value"] == 0.35 and a["threshold"] == 0.1


def test_status_memory_anomaly():
    r = _evaluate(FakeProm(mem={**{n: 150.0 for n in pod_names()}, PP: 512.0}))
    assert r["anomalies"][0]["metric"] == "memory"


def test_status_prometheus_unavailable_is_not_normal():
    assert _evaluate(FakeProm(down=True))["status"] == "prometheus_unavailable"


def test_status_missing_metrics_is_not_normal():
    r = _evaluate(FakeProm(missing={PP}))
    assert r["status"] == "metrics_unavailable"
    assert {m["metric"] for m in r["missing_metrics"]} == {"cpu", "memory"}


def test_status_crashloop_is_anomalous_even_without_prometheus():
    r = _evaluate(FakeProm(down=True), bookinfo_snapshot(broken_ratings=True))
    assert r["status"] == "anomalous"
    assert r["anomalies"][0]["metric"] == "pod_status"
