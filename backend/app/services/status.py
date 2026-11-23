"""
Deterministic status / anomaly detection - no LLM involved.

Lab 3 asked the LLM to fill in a status report; here the status is CALCULATED, so it is
repeatable and testable. The thresholds come from environment variables
(CPU_THRESHOLD_CORES, MEMORY_THRESHOLD_MIB).

Overall status, in priority order:
  anomalous               a pod exceeds a threshold or is CrashLoopBackOff / not ready / ...
  prometheus_unavailable  Prometheus cannot be reached, so CPU/memory cannot be judged
  metrics_unavailable     Prometheus works, but some running pod has no CPU or memory sample
  normal                  every running pod has data and is below every threshold

A missing metric is NEVER treated as healthy.
"""
NORMAL = "normal"
ANOMALOUS = "anomalous"
PROM_DOWN = "prometheus_unavailable"
NO_METRICS = "metrics_unavailable"


def evaluate(pods: list[dict], metrics: dict, cpu_threshold: float, memory_threshold: float,
             service_of: dict[str, str] | None = None) -> dict:
    """
    pods     : pod summaries from discovery.link_pods()
    metrics  : MetricsService.current_by_pod() result
    service_of: pod name -> logical service name (for messages)
    """
    service_of = service_of or {}
    findings: list[dict] = []
    missing: list[dict] = []
    prom_ok = metrics.get("available", False)

    for p in pods:
        if p.get("terminating"):
            continue
        base = {"pod": p["name"], "service": service_of.get(p["name"]), "deployment": p.get("deployment")}

        for problem in p.get("problems", []):
            findings.append({**base, "metric": "pod_status", "value": None, "threshold": None,
                             "severity": "critical", "message": f"{p['name']}: {problem}"})

        if not prom_ok or p.get("phase") != "Running":
            continue
        cpu = metrics["cpu"].get(p["name"])
        mem = metrics["memory"].get(p["name"])
        if cpu is None:
            missing.append({**base, "metric": "cpu"})
        elif cpu > cpu_threshold:
            findings.append({**base, "metric": "cpu", "value": round(cpu, 5), "threshold": cpu_threshold,
                             "unit": "cores", "severity": "warning",
                             "message": f"{p['name']} CPU {cpu:.4f} cores > threshold {cpu_threshold} cores"})
        if mem is None:
            missing.append({**base, "metric": "memory"})
        elif mem > memory_threshold:
            findings.append({**base, "metric": "memory", "value": round(mem, 2), "threshold": memory_threshold,
                             "unit": "MiB", "severity": "warning",
                             "message": f"{p['name']} memory {mem:.1f} MiB > threshold {memory_threshold} MiB"})

    if findings:
        overall = ANOMALOUS
    elif not prom_ok:
        overall = PROM_DOWN
    elif missing:
        overall = NO_METRICS
    elif not pods:
        overall = NO_METRICS
    else:
        overall = NORMAL

    return {
        "status": overall,
        "prometheus_available": prom_ok,
        "prometheus_error": metrics.get("error"),
        "thresholds": {"cpu_cores": cpu_threshold, "memory_mib": memory_threshold},
        "anomalies": findings,
        "missing_metrics": missing,
        "pods_evaluated": len([p for p in pods if not p.get("terminating")]),
    }


def service_status(health: str, evaluation: dict) -> str:
    """Combine Kubernetes health with the metric evaluation for one service card."""
    if health in ("Down", "Degraded"):
        return ANOMALOUS
    return evaluation["status"]
