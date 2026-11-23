"""
Read-only tool implementations for the AI OpsAgent.

They are plain functions (no LangChain import) so they can be unit-tested without an LLM.
Each one calls PlatformService - the same code that feeds the dashboard - and returns a compact
JSON-serialisable dict. None of them can change the cluster: PlatformService has no write method.

Replaces the Lab 3 tools (docker build/run, kubectl apply, file write, exec), which were
WRITE tools for a deployment task and are therefore NOT reused here.
"""
from app.errors import PlatformError


def _err(e: Exception) -> dict:
    if isinstance(e, PlatformError):
        return {"error": e.code, "message": e.message, "details": e.details}
    return {"error": type(e).__name__, "message": str(e)[:300]}


def _service_filter(pods: list[dict], service: str) -> list[dict]:
    return [p for p in pods if not service or p.get("service") == service]


def get_services(platform) -> dict:
    try:
        data = platform.list_services()
    except Exception as e:
        return _err(e)
    return {"prometheus_available": data["meta"].get("prometheus_available"),
            "services": [{k: c[k] for k in ("name", "health", "health_reason", "status", "ready_replicas",
                                            "desired_replicas", "pod_count", "versions", "deployments",
                                            "cpu_cores", "memory_mib", "metrics_state", "restart_count")}
                         for c in data["services"]]}


def get_deployments(platform, service: str = "") -> dict:
    try:
        names = [service] if service else [c["name"] for c in platform.list_services()["services"]]
        out = []
        for n in names:
            w = platform.service_workloads(n)
            for d in w["deployments"]:
                out.append({"service": n, "deployment": d["name"], "version": d["version"],
                            "ready_replicas": d["ready_replicas"], "desired_replicas": d["desired_replicas"],
                            "images": d["images"], "replicasets": [r["name"] for r in d["replicasets"]]})
        return {"deployments": out}
    except Exception as e:
        return _err(e)


def get_pods(platform, service: str = "") -> dict:
    try:
        data = platform.pods()
    except Exception as e:
        return _err(e)
    return {
        "note": ("'ready' is the CURRENT readiness. Past readiness-probe failures are only visible as "
                 "'Unhealthy' Warning events - use get_pod_events for them."),
        "pods": [{"pod": p["name"], "service": p.get("service"), "deployment": p["deployment"],
                  "version": p["version"], "phase": p["phase"], "ready_now": p["ready"],
                  "containers_ready": f'{p["ready_containers"]}/{p["total_containers"]}',
                  "restarts": p["restart_count"], "node": p["node_name"], "problems": p["problems"],
                  "containers": [{"name": c["name"], "ready_now": c["ready"],
                                  "readiness_probe": (c["readiness_probe"]["handler"]
                                                      if c["readiness_probe"]["configured"] else "none defined"),
                                  "liveness_probe": (c["liveness_probe"]["handler"]
                                                     if c["liveness_probe"]["configured"] else "none defined")}
                                 for c in p["containers"]]}
                 for p in _service_filter(data["pods"], service)]}


def _usage(platform, key: str, unit: str, service: str, pod_contains: str) -> dict:
    try:
        data = platform.pods()
    except Exception as e:
        return _err(e)
    if not data["meta"].get("prometheus_available"):
        return {"error": "PROMETHEUS_UNAVAILABLE", "message": data["meta"].get("prometheus_error"),
                "note": "No CPU/memory values can be given; do not guess them."}
    pods = [p for p in _service_filter(data["pods"], service) if pod_contains in p["name"]]
    known = sorted([p for p in pods if p[key] is not None], key=lambda p: p[key], reverse=True)
    return {"unit": unit,
            "pods_sorted_highest_first": [{"pod": p["name"], "service": p.get("service"),
                                           "version": p["version"], key: p[key]} for p in known],
            "pods_without_data": [p["name"] for p in pods if p[key] is None]}


def get_pod_cpu_usage(platform, service: str = "", pod_name_contains: str = "") -> dict:
    return _usage(platform, "cpu_cores", "cores (1.0 = one CPU core, rate over the last window)",
                  service, pod_name_contains)


def get_pod_memory_usage(platform, service: str = "", pod_name_contains: str = "") -> dict:
    return _usage(platform, "memory_mib", "MiB (container_memory_working_set_bytes)", service, pod_name_contains)


def get_container_restarts(platform, service: str = "") -> dict:
    try:
        data = platform.pods()
    except Exception as e:
        return _err(e)
    rows = [{"pod": p["name"], "service": p.get("service"), "container": c["name"],
             "restarts": c["restart_count"], "last_terminated_reason": c["last_terminated_reason"],
             "last_terminated_at": c["last_terminated_at"]}
            for p in _service_filter(data["pods"], service) for c in p["containers"]]
    restarted = sorted([r for r in rows if r["restarts"] > 0], key=lambda r: r["restarts"], reverse=True)
    return {"source": "Kubernetes API (cumulative restartCount since the pod was created)",
            "containers_with_restarts": restarted,
            "containers_without_restarts": len(rows) - len(restarted)}


def get_pod_events(platform, service: str = "", pod: str = "", warnings_only: bool = True) -> dict:
    try:
        events = platform.service_events(service)["events"] if service else platform.events()["events"]
    except Exception as e:
        return _err(e)
    if pod:
        events = [e for e in events if pod in (e["object_name"] or "")]
    if warnings_only:
        events = [e for e in events if e["type"] == "Warning"]
    probe_failures = [{"pod": e["object_name"], "count": e["count"], "last_seen": e["last_seen"],
                       "message": (e["message"] or "")[:200]}
                      for e in events if e["reason"] == "Unhealthy"]
    return {"count": len(events), "probe_failures": probe_failures, "events": events[:20],
            "note": "Kubernetes keeps events for about one hour only. 'Unhealthy' = a readiness or "
                    "liveness probe failed at that time."}


def get_service_health(platform, service: str) -> dict:
    try:
        d = platform.service_detail(service)
    except Exception as e:
        return _err(e)
    diag = d["diagnostics"]
    return {
        "service": service,
        "health": d["summary"]["health"], "health_reason": d["summary"]["health_reason"],
        "status": d["summary"]["status"],
        "replicas": f'{d["summary"]["ready_replicas"]}/{d["summary"]["desired_replicas"]}',
        "versions": d["summary"]["versions"],
        "pods": [{"pod": p["name"], "version": p["version"], "phase": p["phase"], "ready": p["ready"],
                  "restarts": p["restart_count"], "cpu_cores": p["cpu_cores"], "memory_mib": p["memory_mib"],
                  "problems": p["problems"]} for p in d["pods"]],
        "anomalies": diag["status"]["anomalies"],
        "missing_metrics": diag["status"]["missing_metrics"],
        "crashloop_pods": diag["crashloop_pods"], "not_ready_pods": diag["not_ready_pods"],
        "recent_warning_events": [f'{e["reason"]}: {e["message"]}' for e in diag["warning_events"][:5]],
        "resource_requests_or_limits_configured": diag["resources_configured"],
        "istio_routes": [{"virtual_service": v["name"],
                          "routes": [{"subset": r["subset"], "weight": r["weight"]} for r in v["routes"]]}
                         for v in d["istio"]["virtual_services"]],
        "dependencies": {k: d["dependencies"].get(k) for k in ("available", "source", "calls", "called_by", "note")},
    }


def get_metric_trend(platform, service: str, metric: str = "cpu", minutes: int = 15) -> dict:
    if metric not in ("cpu", "memory") or minutes not in (5, 15, 60):
        return {"error": "INVALID_INPUT", "message": "metric must be cpu|memory, minutes 5|15|60"}
    try:
        h = platform.service_history(service, metric, minutes)
    except Exception as e:
        return _err(e)
    out = []
    for s in h["series"]:
        vals = [p["v"] for p in s["points"] if p["v"] is not None]
        out.append({"pod": s["name"], "samples": len(vals),
                    "min": min(vals) if vals else None, "max": max(vals) if vals else None,
                    "avg": round(sum(vals) / len(vals), 5) if vals else None,
                    "latest": vals[-1] if vals else None})
    return {"service": service, "metric": metric, "unit": h["unit"], "minutes": minutes, "per_pod": out}


def get_prometheus_status(platform) -> dict:
    h = platform.health()
    return {"prometheus": h["prometheus"], "kubernetes": {k: h["kubernetes"].get(k) for k in ("ok", "context", "version", "error")}}


def get_anomaly_status(platform) -> dict:
    try:
        s = platform.status()
    except Exception as e:
        return _err(e)
    return {k: s[k] for k in ("status", "prometheus_available", "prometheus_error", "thresholds",
                              "anomalies", "missing_metrics", "services")}


# name -> (function, description, {arg: (type, default, help)})
TOOL_SPECS = {
    "get_services": (get_services, "List the Bookinfo logical services with health, status, replicas, "
                     "versions, total CPU (cores), memory (MiB) and restarts.", {}),
    "get_deployments": (get_deployments, "List Deployments (workload versions such as reviews-v1/v2/v3) "
                        "with ready/desired replicas, images and ReplicaSets.",
                        {"service": (str, "", "service name, empty = all")}),
    "get_pods": (get_pods, "List pods with CURRENT phase/readiness, the probes defined per container, restarts, "
                 "node and problems (CrashLoopBackOff, not ready, ...). Does NOT show past probe failures.",
                 {"service": (str, "", "service name, empty = all")}),
    "get_pod_cpu_usage": (get_pod_cpu_usage, "Current CPU usage per pod in cores, highest first.",
                          {"service": (str, "", "service name, empty = all"),
                           "pod_name_contains": (str, "", "e.g. reviews-v1")}),
    "get_pod_memory_usage": (get_pod_memory_usage, "Current memory working set per pod in MiB, highest first.",
                             {"service": (str, "", "service name, empty = all"),
                              "pod_name_contains": (str, "", "e.g. productpage")}),
    "get_container_restarts": (get_container_restarts, "Containers that have restarted, with the last "
                               "termination reason.", {"service": (str, "", "service name, empty = all")}),
    "get_pod_events": (get_pod_events, "Recent Kubernetes events (warnings by default), including readiness/"
                       "liveness probe failures ('Unhealthy') of the last hour.",
                       {"service": (str, "", "service name, empty = whole namespace"),
                        "pod": (str, "", "part of a pod name"),
                        "warnings_only": (bool, True, "only Warning events")}),
    "get_service_health": (get_service_health, "Full health report of ONE service: pods, anomalies, "
                           "missing metrics, events, Istio routes and dependencies.",
                           {"service": (str, ..., "productpage, details, ratings or reviews")}),
    "get_metric_trend": (get_metric_trend, "Min/avg/max/latest CPU or memory per pod of a service over "
                         "the last 5, 15 or 60 minutes.",
                         {"service": (str, ..., "service name"), "metric": (str, "cpu", "cpu or memory"),
                          "minutes": (int, 15, "5, 15 or 60")}),
    "get_prometheus_status": (get_prometheus_status, "Whether Prometheus and Kubernetes are reachable.", {}),
    "get_anomaly_status": (get_anomaly_status, "Deterministic anomaly check against the CPU/memory "
                           "thresholds, with the offending pod and metric.", {}),
}
