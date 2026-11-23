"""
PromQL catalogue and metric collection. No LLM is involved here.

The CPU / memory / restart queries are the ones used in Lab 2 (bookinfo_monitor_v2.py), now with:
  * CPU in CORES (Lab 2 used millicores), memory in MiB;
  * container!="" and container!="POD" to drop the cgroup roll-up and pause containers;
  * an optional pod regex built from Deployment names, so history survives pod restarts;
  * missing pods reported as None instead of 0.

Metric sources (kube-prometheus-stack):
  container_cpu_usage_seconds_total       cAdvisor (kubelet)
  container_memory_working_set_bytes      cAdvisor (kubelet)
  kube_pod_container_status_restarts_total  kube-state-metrics
  kube_pod_status_ready                   kube-state-metrics
"""
import re
import time

from app.errors import PrometheusQueryError, PrometheusUnavailable

RANGE_STEPS = {5: 15, 15: 30, 60: 60}  # minutes -> step seconds
ALLOWED_MINUTES = tuple(RANGE_STEPS)

_NAME_OK = re.compile(r"^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$")


def pod_regex(deployment_names: list[str]) -> str | None:
    """Regex that matches every pod created by these Deployments: <deployment>-<rs-hash>-<pod-id>."""
    names = [n for n in deployment_names if n and _NAME_OK.match(n)]
    if not names:
        return None
    alts = "|".join(n.replace(".", "\\\\.") for n in sorted(names))
    return f"({alts})-[a-z0-9]+-[a-z0-9]+"


def _sel(namespace: str, pod_re: str | None, containers: bool = True) -> str:
    parts = [f'namespace="{namespace}"']
    if containers:
        parts += ['container!=""', 'container!="POD"']
    if pod_re:
        parts.append(f'pod=~"{pod_re}"')
    return ",".join(parts)


def q_cpu(namespace: str, window: str, pod_re: str | None = None, by: str = "pod") -> str:
    return f"sum by ({by}) (rate(container_cpu_usage_seconds_total{{{_sel(namespace, pod_re)}}}[{window}]))"


def q_memory(namespace: str, pod_re: str | None = None, by: str = "pod") -> str:
    return f"sum by ({by}) (container_memory_working_set_bytes{{{_sel(namespace, pod_re)}}}) / 1048576"


def q_restarts(namespace: str, pod_re: str | None = None) -> str:
    return f"sum by (pod, container) (kube_pod_container_status_restarts_total{{{_sel(namespace, pod_re, False)}}})"


def q_pod_ready(namespace: str) -> str:
    return f'sum by (pod) (kube_pod_status_ready{{namespace="{namespace}",condition="true"}})'


def round_or_none(v: float | None, digits: int) -> float | None:
    return None if v is None else round(v, digits)


class MetricsService:
    def __init__(self, prom, namespace: str, rate_window: str = "2m"):
        self.prom = prom
        self.namespace = namespace
        self.window = rate_window

    # ---------------------------------------------------------------- status
    def status(self) -> dict:
        try:
            info = self.prom.buildinfo()
            return {"available": True, "version": info.get("version"), "error": None}
        except (PrometheusUnavailable, PrometheusQueryError) as e:
            return {"available": False, "version": None, "error": e.message}

    # ---------------------------------------------------------------- instant values
    def current_by_pod(self, pod_re: str | None = None) -> dict:
        """{'available': bool, 'error': str|None, 'cpu': {pod: cores|None}, 'memory': {pod: MiB|None},
        'queries': {...}} - a pod that is missing from a dict has NO data (not zero)."""
        queries = {"cpu": q_cpu(self.namespace, self.window, pod_re),
                   "memory": q_memory(self.namespace, pod_re)}
        out = {"available": True, "error": None, "cpu": {}, "memory": {}, "queries": queries,
               "collected_at": time.time()}
        try:
            for key, q in queries.items():
                out[key] = {s["labels"].get("pod", "?"): s["value"] for s in self.prom.query(q)}
        except (PrometheusUnavailable, PrometheusQueryError) as e:
            out.update(available=False, error=e.message, error_code=e.code, cpu={}, memory={})
        return out

    def current_by_container(self, pod_re: str | None = None) -> dict:
        queries = {"cpu": q_cpu(self.namespace, self.window, pod_re, by="pod, container"),
                   "memory": q_memory(self.namespace, pod_re, by="pod, container")}
        out = {"available": True, "error": None, "items": {}, "queries": queries}
        try:
            for key, q in queries.items():
                for s in self.prom.query(q):
                    k = (s["labels"].get("pod", "?"), s["labels"].get("container", "?"))
                    out["items"].setdefault(k, {})[key] = s["value"]
        except (PrometheusUnavailable, PrometheusQueryError) as e:
            out.update(available=False, error=e.message, items={})
        return out

    def restarts(self, pod_re: str | None = None) -> dict:
        q = q_restarts(self.namespace, pod_re)
        try:
            samples = self.prom.query(q)
        except (PrometheusUnavailable, PrometheusQueryError) as e:
            return {"available": False, "error": e.message, "items": [], "query": q}
        items = [{"pod": s["labels"].get("pod"), "container": s["labels"].get("container"),
                  "restarts": None if s["value"] is None else int(s["value"])} for s in samples]
        return {"available": True, "error": None, "query": q,
                "items": sorted(items, key=lambda i: (i["pod"] or "", i["container"] or ""))}

    # ---------------------------------------------------------------- history
    def history(self, metric: str, minutes: int, pod_re: str | None = None, by: str = "pod") -> dict:
        if minutes not in RANGE_STEPS:
            raise ValueError(f"minutes must be one of {ALLOWED_MINUTES}")
        step = RANGE_STEPS[minutes]
        q = q_cpu(self.namespace, self.window, pod_re, by) if metric == "cpu" else q_memory(self.namespace, pod_re, by)
        end = time.time()
        series = self.prom.query_range(q, end - minutes * 60, end, step)
        digits = 5 if metric == "cpu" else 2
        for s in series:
            s["name"] = s["labels"].get("pod", "?") if by == "pod" else \
                f'{s["labels"].get("pod", "?")}/{s["labels"].get("container", "?")}'
            s["points"] = [{"t": p["t"], "v": round_or_none(p["v"], digits)} for p in s["points"]]
        return {
            "metric": metric,
            "unit": "cores" if metric == "cpu" else "MiB",
            "minutes": minutes,
            "step_seconds": step,
            "query": q,
            "series": sorted(series, key=lambda s: s["name"]),
        }

    # ---------------------------------------------------------------- service traffic (Istio)
    def istio_edges(self, window: str = "15m") -> dict:
        q = ("sum by (source_workload, source_workload_namespace, destination_workload, "
             "destination_service_name) (rate(istio_requests_total{reporter=\"destination\","
             f"destination_workload_namespace=\"{self.namespace}\"}}[{window}]))")
        try:
            samples = self.prom.query(q)
        except (PrometheusUnavailable, PrometheusQueryError) as e:
            return {"available": False, "error": e.message, "edges": [], "query": q}
        edges = [{"source_workload": s["labels"].get("source_workload"),
                  "destination_workload": s["labels"].get("destination_workload"),
                  "destination_service": s["labels"].get("destination_service_name"),
                  "requests_per_second": round_or_none(s["value"], 4)} for s in samples]
        return {"available": True, "error": None, "edges": edges, "query": q}


def attach_metrics(pods: list[dict], metrics: dict) -> list[dict]:
    """Add cpu_cores / memory_mib to pod dicts. None (never 0) when a value is missing."""
    for p in pods:
        cpu = metrics["cpu"].get(p["name"]) if metrics["available"] else None
        mem = metrics["memory"].get(p["name"]) if metrics["available"] else None
        p["cpu_cores"] = round_or_none(cpu, 5)
        p["memory_mib"] = round_or_none(mem, 2)
        if not metrics["available"]:
            p["metrics_state"] = "prometheus_unavailable"
        elif cpu is None or mem is None:
            p["metrics_state"] = "metrics_unavailable"
        else:
            p["metrics_state"] = "ok"
    return pods


def sum_or_none(values: list[float | None]) -> float | None:
    """Sum of known values; None if there is no known value at all."""
    known = [v for v in values if v is not None]
    return sum(known) if known else None
