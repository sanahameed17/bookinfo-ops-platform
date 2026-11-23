"""
AI agent: read-only tool implementations (run everywhere) and the LangChain runner with a fake
LLM (runs when langchain is installed - i.e. on your machine, skipped otherwise).
"""
import json
from types import SimpleNamespace

import pytest

from app.agent import tool_impls as t
from app.agent.loop_guard import LoopGuard
from app.errors import LLMError, LLMNotConfigured
from app.services.platform import PlatformService
from tests.fakes import FakeK8s, FakeProm, bookinfo_snapshot, pod_names, settings

PP = "productpage-v1-544855df4c-njtnf"


def platform(prom=None, k8s=None):
    return PlatformService(settings(), k8s or FakeK8s(), prom or FakeProm())


# ------------------------------------------------------------------ tools (no LLM)
def test_tools_are_read_only_by_name():
    # every tool is a "get_" reader; PlatformService has no write method at all
    assert all(n.startswith("get_") for n in t.TOOL_SPECS)
    from app.clients import k8s_client
    src = open(k8s_client.__file__, encoding="utf-8").read()
    for verb in ("create_namespaced", "delete_namespaced", "patch_namespaced", "replace_namespaced",
                 "connect_get_namespaced_pod_exec"):
        assert verb not in src


def test_get_services_tool():
    r = t.get_services(platform())
    assert [s["name"] for s in r["services"]] == ["details", "productpage", "ratings", "reviews"]


def test_cpu_tool_sorted_highest_first():
    cpu = {n: 0.01 for n in pod_names()}
    cpu[PP] = 0.09
    r = t.get_pod_cpu_usage(platform(FakeProm(cpu=cpu)))
    assert r["pods_sorted_highest_first"][0]["pod"] == PP


def test_cpu_tool_compares_reviews_versions():
    r = t.get_pod_cpu_usage(platform(), service="reviews")
    assert {p["version"] for p in r["pods_sorted_highest_first"]} == {"v1", "v2", "v3"}


def test_cpu_tool_refuses_to_guess_when_prometheus_down():
    r = t.get_pod_cpu_usage(platform(FakeProm(down=True)))
    assert r["error"] == "PROMETHEUS_UNAVAILABLE" and "do not guess" in r["note"]


def test_restart_tool():
    r = t.get_container_restarts(platform())
    assert r["containers_with_restarts"][0]["restarts"] == 21


def test_service_health_tool_and_unknown_service():
    assert t.get_service_health(platform(), "reviews")["versions"] == ["v1", "v2", "v3"]
    assert t.get_service_health(platform(), "nope")["error"] == "SERVICE_NOT_FOUND"


def test_unhealthy_pods_found():
    r = t.get_pods(platform(k8s=FakeK8s(bookinfo_snapshot(broken_ratings=True))))
    bad = [p for p in r["pods"] if p["problems"]]
    assert bad and bad[0]["service"] == "ratings"


def test_anomaly_tool():
    assert t.get_anomaly_status(platform())["status"] == "normal"


def test_loop_guard_blocks_identical_call():
    g = LoopGuard()
    f = g.wrap("x", lambda **k: "ok")
    assert f(a=1) == "ok" and "LOOP GUARD" in f(a=1) and f(a=2) == "ok"


# ------------------------------------------------------------------ runner
def _settings(key="sk-secret-123456789"):
    return SimpleNamespace(llm_configured=bool(key), effective_llm_api_key=key,
                           effective_llm_base_url="https://api.deepseek.com", effective_llm_model="deepseek-chat",
                           llm_timeout_seconds=5, llm_max_iterations=6, k8s_namespace="bookinfo",
                           cpu_threshold_cores=0.1, memory_threshold_mib=400.0)


def test_agent_not_configured():
    from app.agent.runner import AgentRunner
    with pytest.raises(LLMNotConfigured):
        AgentRunner(_settings(key=""), platform()).ask("hi")


def test_agent_calls_real_tool_and_reports_evidence():
    pytest.importorskip("langchain_classic")
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from app.agent.runner import AgentRunner

    step1 = 'Action:\n```\n{"action": "get_pod_cpu_usage", "action_input": {}}\n```'
    step2 = 'Action:\n```\n{"action": "Final Answer", "action_input": "productpage-v1 uses the most CPU."}\n```'
    runner = AgentRunner(_settings(), platform())
    runner._llm = lambda: FakeListChatModel(responses=[step1, step2])
    out = runner.ask("Which Bookinfo Pod is using the most CPU?")
    assert out["answer"] == "productpage-v1 uses the most CPU."
    assert out["tools_used"][0]["tool"] == "get_pod_cpu_usage"
    assert "pods_sorted_highest_first" in out["tools_used"][0]["output_preview"]


def test_agent_llm_error_is_structured_and_hides_key():
    pytest.importorskip("langchain_classic")
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from app.agent.runner import AgentRunner

    class AuthenticationError(Exception):
        pass

    class Broken(FakeListChatModel):
        def _call(self, *a, **k):
            raise AuthenticationError("Incorrect API key provided: sk-secret-123456789")

    runner = AgentRunner(_settings(), platform())
    runner._llm = lambda: Broken(responses=["x"])
    with pytest.raises(LLMError) as e:
        runner.ask("hi")
    assert "rejected the API key" in e.value.message
    assert "sk-secret-123456789" not in json.dumps(e.value.to_dict())
