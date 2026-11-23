"""
HTTP API tests with FastAPI's TestClient. The real Kubernetes / Prometheus clients are replaced by
fakes through dependency_overrides, so no cluster is needed.
Needs: fastapi, httpx, pydantic-settings (pip install -r requirements-dev.txt).
"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("pydantic_settings")

from fastapi.testclient import TestClient  # noqa: E402

from app.deps import get_agent_runner, get_platform  # noqa: E402
from app.errors import LLMError  # noqa: E402
from app.main import app  # noqa: E402
from app.services.platform import PlatformService  # noqa: E402
from tests.fakes import FakeK8s, FakeProm, bookinfo_snapshot, settings  # noqa: E402


@pytest.fixture
def client():
    def make(prom=None, k8s=None):
        app.dependency_overrides[get_platform] = lambda: PlatformService(settings(), k8s or FakeK8s(),
                                                                         prom or FakeProm())
        return TestClient(app)
    yield make
    app.dependency_overrides.clear()


def test_health(client):
    r = client().get("/api/health")
    assert r.status_code == 200
    assert r.json()["kubernetes"]["ok"] and r.json()["prometheus"]["available"]


def test_overview(client):
    body = client().get("/api/cluster/overview").json()
    assert body["totals"]["microservices"] == 4 and body["totals"]["pods"] == 6


def test_services_list_and_detail(client):
    c = client()
    names = [s["name"] for s in c.get("/api/services").json()["services"]]
    assert names == ["details", "productpage", "ratings", "reviews"]
    d = c.get("/api/services/reviews").json()
    assert [x["name"] for x in d["deployments"]] == ["reviews-v1", "reviews-v2", "reviews-v3"]
    assert d["service"]["ports"][0]["port"] == 9080


@pytest.mark.parametrize("path", ["workloads", "pods", "events", "metrics/cpu?minutes=5",
                                  "metrics/memory?minutes=60"])
def test_service_sub_endpoints(client, path):
    assert client().get(f"/api/services/productpage/{path}").status_code == 200


def test_unknown_service_is_404_with_structured_error(client):
    r = client().get("/api/services/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SERVICE_NOT_FOUND"


def test_invalid_service_name_and_range(client):
    assert client().get("/api/services/Bad_Name").status_code == 422
    r = client().get("/api/metrics/cpu?minutes=7")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_RANGE"


def test_namespace_metrics(client):
    c = client()
    assert c.get("/api/metrics/cpu?minutes=15").json()["unit"] == "cores"
    assert c.get("/api/metrics/memory").json()["unit"] == "MiB"
    assert c.get("/api/metrics/restarts").json()["prometheus"]["available"] is True


def test_empty_metrics(client):
    body = client(FakeProm(empty=True)).get("/api/services").json()
    assert all(s["cpu_cores"] is None for s in body["services"])
    assert all(s["metrics_state"] == "metrics_unavailable" for s in body["services"])


def test_prometheus_failure(client):
    c = client(FakeProm(down=True))
    assert c.get("/api/services").status_code == 200  # inventory still works
    r = c.get("/api/metrics/cpu")
    assert r.status_code == 503 and r.json()["error"]["code"] == "PROMETHEUS_UNAVAILABLE"
    assert c.get("/api/status").json()["status"] == "prometheus_unavailable"


def test_status_detects_crashloop(client):
    body = client(k8s=FakeK8s(bookinfo_snapshot(broken_ratings=True))).get("/api/status").json()
    assert body["status"] == "anomalous"


def test_config_has_no_secrets(client):
    body = client().get("/api/config").json()
    assert "llm_api_key" not in body and "openai_api_key" not in body


def test_chat_llm_error_is_502(client):
    class R:
        def ask(self, *a, **k):
            raise LLMError("The LLM provider rejected the API key (check LLM_API_KEY).")
    app.dependency_overrides[get_agent_runner] = lambda: R()
    r = client().post("/api/chat", json={"message": "hi"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "LLM_API_ERROR"


def test_chat_validation(client):
    assert client().post("/api/chat", json={"message": ""}).status_code == 422
