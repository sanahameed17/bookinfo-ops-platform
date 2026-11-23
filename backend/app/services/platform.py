"""
PlatformService - the one place that combines Kubernetes discovery, Prometheus metrics,
deterministic status and Istio/Jaeger topology. The REST API and the AI agent tools both call
this class, so the dashboard and the agent always see the same facts.
"""
import logging
from datetime import datetime, timezone

from app.errors import PrometheusQueryError, PrometheusUnavailable, ServiceNotFound
from app.services import discovery, status as status_mod, topology
from app.services.metrics import MetricsService, attach_metrics, pod_regex, sum_or_none

log = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PlatformService:
    def __init__(self, settings, k8s, prom, jaeger=None):
        self.settings = settings
        self.k8s = k8s
        self.prom = prom
        self.jaeger = jaeger
        self.ns = settings.k8s_namespace
        self.metrics = MetricsService(prom, self.ns, settings.prometheus_rate_window)

    # ------------------------------------------------------------------ helpers
    def meta(self, **extra) -> dict:
        return {"namespace": self.ns, "generated_at": now_iso(),
                "kubernetes_context": self.k8s.active_context or self.settings.k8s_context, **extra}

    def _snapshot(self) -> dict:
        return self.k8s.snapshot(self.ns)

    def _view(self, name: str) -> dict:
        view = discovery.find_service(self._snapshot(), name)
        if view is None:
            names = [s["metadata"]["name"] for s in self._snapshot()["services"]]
            raise ServiceNotFound(f"Service '{name}' not found in namespace '{self.ns}'",
                                  {"available_services": names})
        return view

    def _service_of(self, inventory: list[dict]) -> dict[str, str]:
        return {p["name"]: v["service"]["name"] for v in inventory for p in v["pods"]}

    @staticmethod
    def _pod_re(view: dict) -> str | None:
        return pod_regex([d["name"] for d in view["deployments"]])

    def _card(self, view: dict, metrics: dict) -> dict:
        pods = attach_metrics([dict(p) for p in view["pods"]], metrics)
        ev = status_mod.evaluate(pods, metrics, self.settings.cpu_threshold_cores,
                                 self.settings.memory_threshold_mib)
        cpu = sum_or_none([p["cpu_cores"] for p in pods]) if metrics["available"] else None
        mem = sum_or_none([p["memory_mib"] for p in pods]) if metrics["available"] else None
        return {
            "name": view["service"]["name"],
            "health": view["health"],
            "health_reason": view["health_reason"],
            "status": status_mod.service_status(view["health"], ev),
            "ready_replicas": view["ready_replicas"],
            "desired_replicas": view["desired_replicas"],
            "pod_count": len(view["pods"]),
            "ready_pods": sum(1 for p in view["pods"] if p["healthy"]),
            "versions": view["versions"],
            "version_count": len(view["deployments"]),
            "deployments": [d["name"] for d in view["deployments"]],
            "cpu_cores": None if cpu is None else round(cpu, 5),
            "memory_mib": None if mem is None else round(mem, 2),
            "metrics_state": ("prometheus_unavailable" if not metrics["available"] else
                              "ok" if all(p["metrics_state"] == "ok" for p in pods) and pods else
                              "metrics_unavailable"),
            "restart_count": view["restart_count"],
            "anomalies": ev["anomalies"],
            "updated_at": now_iso(),
        }

    # ------------------------------------------------------------------ health
    def health(self) -> dict:
        k8s = {"ok": False, "context": None, "server": None, "version": None, "error": None}
        try:
            v = self.k8s.version()
            k8s.update(ok=True, version=v.get("gitVersion"))
        except Exception as e:  # report, never crash the health endpoint
            k8s["error"] = getattr(e, "message", str(e))
            k8s["details"] = getattr(e, "details", None)
        k8s["context"], k8s["server"] = self.k8s.active_context, self.k8s.server
        prom = self.metrics.status()
        prom["url"] = self.settings.prometheus_url
        return {"status": "ok" if k8s["ok"] and prom["available"] else "degraded",
                "kubernetes": k8s, "prometheus": prom,
                "llm_configured": self.settings.llm_configured, "generated_at": now_iso()}

    # ------------------------------------------------------------------ overview
    def overview(self) -> dict:
        snap = self._snapshot()
        inventory = discovery.build_inventory(snap)
        pods = discovery.link_pods(snap)
        metrics = self.metrics.current_by_pod()
        attach_metrics(pods, metrics)
        warnings = []
        try:
            capacity = discovery.cluster_capacity(self.k8s.list_nodes())
        except Exception as e:
            capacity = None
            warnings.append(f"Node capacity not readable: {getattr(e, 'message', e)}")
        try:
            chaos = self.k8s.chaos_experiments(self.ns)
        except Exception:
            chaos = {"installed": False, "items": []}
        active_chaos = [{"kind": c.get("kind"), "name": c["metadata"]["name"],
                         "paused": (c["metadata"].get("annotations") or {}).get(
                             "experiment.chaos-mesh.org/pause") == "true",
                         "created_at": c["metadata"].get("creationTimestamp")} for c in chaos["items"]]
        if active_chaos:
            warnings.append(f"{len(active_chaos)} Chaos Mesh object(s) exist in '{self.ns}' - "
                            "they may explain unhealthy pods.")
        if not metrics["available"]:
            warnings.append(f"Prometheus unavailable: {metrics['error']}")

        cpu_total = sum_or_none([p["cpu_cores"] for p in pods]) if metrics["available"] else None
        mem_total = sum_or_none([p["memory_mib"] for p in pods]) if metrics["available"] else None
        live = [p for p in pods if not p["terminating"]]
        ev = status_mod.evaluate(pods, metrics, self.settings.cpu_threshold_cores,
                                 self.settings.memory_threshold_mib, self._service_of(inventory))
        return {
            "meta": self.meta(),
            "totals": {
                "microservices": len(inventory),
                "deployments": len(snap["deployments"]),
                "pods": len(live),
                "running_pods": sum(1 for p in live if p["phase"] == "Running"),
                "unhealthy_pods": sum(1 for p in live if not p["healthy"]),
                "container_restarts": sum(p["restart_count"] for p in live),
                "cpu_cores": None if cpu_total is None else round(cpu_total, 5),
                "memory_mib": None if mem_total is None else round(mem_total, 2),
                "cpu_percent_of_cluster": (round(100 * cpu_total / capacity["allocatable_cpu_cores"], 2)
                                           if cpu_total is not None and capacity and capacity["allocatable_cpu_cores"] else None),
                "memory_percent_of_cluster": (round(100 * mem_total / capacity["allocatable_memory_mib"], 2)
                                              if mem_total is not None and capacity and capacity["allocatable_memory_mib"] else None),
            },
            "cluster": capacity,
            "prometheus": {"available": metrics["available"], "error": metrics.get("error"),
                           "url": self.settings.prometheus_url},
            "status": ev["status"],
            "anomaly_count": len(ev["anomalies"]),
            "chaos_experiments": active_chaos,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------ services
    def list_services(self) -> dict:
        inventory = discovery.build_inventory(self._snapshot())
        metrics = self.metrics.current_by_pod()
        cards = [self._card(v, metrics) for v in inventory]
        return {"meta": self.meta(prometheus_available=metrics["available"],
                                  prometheus_error=metrics.get("error")),
                "services": cards}

    def service_detail(self, name: str) -> dict:
        view = self._view(name)
        pod_re = self._pod_re(view)
        metrics = self.metrics.current_by_pod(pod_re)
        pods = attach_metrics([dict(p) for p in view["pods"]], metrics)
        containers = self.metrics.current_by_container(pod_re)
        for p in pods:
            for c in p["containers"]:
                vals = containers["items"].get((p["name"], c["name"]), {}) if containers["available"] else {}
                c["cpu_cores"] = None if vals.get("cpu") is None else round(vals["cpu"], 5)
                c["memory_mib"] = None if vals.get("memory") is None else round(vals["memory"], 2)
        ev = status_mod.evaluate(pods, metrics, self.settings.cpu_threshold_cores,
                                 self.settings.memory_threshold_mib)
        card = self._card(view, metrics)
        try:
            istio = topology.istio_for_service(self.k8s.istio_resources(self.ns), name, self.ns)
        except Exception as e:
            istio = {"installed": False, "virtual_services": [], "destination_rules": [], "gateways": [],
                     "note": f"Istio resources not readable: {getattr(e, 'message', e)}"}
        names = {name} | {p["name"] for p in pods} | {d["name"] for d in view["deployments"]} | \
                {r["name"] for r in view["replicasets"]}
        try:
            events = discovery.events_for(self.k8s.list_events(self.ns), names)[:50]
        except Exception:
            events = []
        return {
            "meta": self.meta(),
            "summary": card,
            "service": view["service"],
            "deployments": view["deployments"],
            "replicasets": view["replicasets"],
            "pods": pods,
            "metrics": {"available": metrics["available"], "error": metrics.get("error"),
                        "queries": metrics["queries"],
                        "container_metrics_available": containers["available"]},
            "diagnostics": {
                "status": ev,
                "failed_or_pending_pods": [p["name"] for p in pods if p["phase"] in ("Failed", "Pending")],
                "crashloop_pods": [p["name"] for p in pods
                                   if any(c["state_reason"] == "CrashLoopBackOff" for c in p["containers"])],
                "image_pull_problems": [p["name"] for p in pods if any(
                    c["state_reason"] in ("ImagePullBackOff", "ErrImagePull") for c in p["containers"])],
                "not_ready_pods": [p["name"] for p in pods if not p["ready"]],
                "warning_events": [e for e in events if e["type"] == "Warning"][:10],
                "resources_configured": any(c["requests"] or c["limits"]
                                            for p in pods for c in p["containers"] if not c["is_sidecar"]),
            },
            "istio": istio,
            "dependencies": self.service_dependencies(name),
            "events": events,
        }

    def service_workloads(self, name: str) -> dict:
        view = self._view(name)
        return {"meta": self.meta(), "service": name, "versions": view["versions"],
                "deployments": view["deployments"], "replicasets": view["replicasets"]}

    def service_pods(self, name: str) -> dict:
        view = self._view(name)
        metrics = self.metrics.current_by_pod(self._pod_re(view))
        return {"meta": self.meta(prometheus_available=metrics["available"]), "service": name,
                "pods": attach_metrics([dict(p) for p in view["pods"]], metrics)}

    def service_history(self, name: str, metric: str, minutes: int, by: str = "pod") -> dict:
        view = self._view(name)
        pod_re = self._pod_re(view)
        if pod_re is None:
            return {"meta": self.meta(), "service": name, "metric": metric, "minutes": minutes,
                    "unit": "cores" if metric == "cpu" else "MiB", "series": [], "query": None,
                    "step_seconds": None, "note": "Service has no deployments - nothing to query."}
        return {"meta": self.meta(), "service": name, **self.metrics.history(metric, minutes, pod_re, by)}

    def service_events(self, name: str) -> dict:
        view = self._view(name)
        names = {name} | {p["name"] for p in view["pods"]} | {d["name"] for d in view["deployments"]} | \
                {r["name"] for r in view["replicasets"]}
        return {"meta": self.meta(), "service": name,
                "events": discovery.events_for(self.k8s.list_events(self.ns), names)}

    # ------------------------------------------------------------------ namespace-wide
    def namespace_history(self, metric: str, minutes: int) -> dict:
        return {"meta": self.meta(), **self.metrics.history(metric, minutes)}

    def restarts(self) -> dict:
        prom = self.metrics.restarts()
        k8s_items = [{"pod": p["name"], "container": c["name"], "restarts": c["restart_count"],
                      "last_terminated_reason": c["last_terminated_reason"]}
                     for p in discovery.link_pods(self._snapshot()) for c in p["containers"]]
        return {"meta": self.meta(), "prometheus": prom,
                "kubernetes": {"source": "Kubernetes API containerStatuses.restartCount",
                               "items": sorted(k8s_items, key=lambda i: (i["pod"], i["container"]))}}

    def pods(self) -> dict:
        snap = self._snapshot()
        inventory = discovery.build_inventory(snap)
        service_of = self._service_of(inventory)
        metrics = self.metrics.current_by_pod()
        pods = attach_metrics(discovery.link_pods(snap), metrics)
        for p in pods:
            p["service"] = service_of.get(p["name"])
        return {"meta": self.meta(prometheus_available=metrics["available"],
                                  prometheus_error=metrics.get("error")),
                "pods": sorted(pods, key=lambda p: p["name"])}

    def events(self) -> dict:
        return {"meta": self.meta(), "events": discovery.events_for(self.k8s.list_events(self.ns), set())}

    def status(self) -> dict:
        snap = self._snapshot()
        inventory = discovery.build_inventory(snap)
        pods = discovery.link_pods(snap)
        metrics = self.metrics.current_by_pod()
        ev = status_mod.evaluate(pods, metrics, self.settings.cpu_threshold_cores,
                                 self.settings.memory_threshold_mib, self._service_of(inventory))
        return {"meta": self.meta(), **ev,
                "services": [{"name": v["service"]["name"], "health": v["health"],
                              "health_reason": v["health_reason"]} for v in inventory]}

    # ------------------------------------------------------------------ topology
    def all_edges(self) -> dict:
        inventory = discovery.build_inventory(self._snapshot())
        w2s = {d["name"]: v["service"]["name"] for v in inventory for d in v["deployments"]}
        istio = self.metrics.istio_edges()
        if istio["available"] and istio["edges"]:
            return {"source": "istio_requests_total (Prometheus)", "available": True,
                    "edges": topology.edges_from_istio(istio, w2s), "query": istio["query"], "note": None}
        notes = []
        if not istio["available"]:
            notes.append(f"Prometheus: {istio['error']}")
        else:
            notes.append("Prometheus has no istio_requests_total samples (Envoy sidecars are probably "
                         "not scraped by kube-prometheus-stack).")
        if self.jaeger is not None:
            j = self.jaeger.dependencies()
            if j["available"] and j["items"]:
                return {"source": "Jaeger /api/dependencies (traces, last 24 h)", "available": True,
                        "edges": topology.edges_from_jaeger(j["items"], self.ns), "query": None,
                        "note": " ".join(notes)}
            notes.append(j["error"] or "Jaeger returned no dependencies for the last 24 h.")
        return {"source": None, "available": False, "edges": [], "query": istio.get("query"),
                "note": "Dependency information is unavailable. " + " ".join(notes)}

    def service_dependencies(self, name: str) -> dict:
        try:
            edges = self.all_edges()
        except (PrometheusUnavailable, PrometheusQueryError) as e:
            return {"available": False, "source": None, "calls": [], "called_by": [], "edges": [],
                    "note": f"Dependency information is unavailable: {e.message}"}
        if not edges["available"]:
            return {"available": False, "source": None, "calls": [], "called_by": [], "edges": [],
                    "note": edges["note"]}
        return {"available": True, "source": edges["source"], "note": edges["note"],
                **topology.dependencies_for(name, edges["edges"])}
