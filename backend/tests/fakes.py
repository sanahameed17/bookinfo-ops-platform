"""
Test doubles: a realistic Bookinfo namespace as plain Kubernetes JSON, and fake
Kubernetes / Prometheus clients. Shaped like `kubectl get -o json` output.
"""
from types import SimpleNamespace

NS = "bookinfo"


def deployment(name, app, version, replicas=1, ready=1):
    return {
        "metadata": {"name": name, "namespace": NS, "uid": f"uid-{name}",
                     "creationTimestamp": "2026-10-13T08:00:00Z"},
        "spec": {"replicas": replicas,
                 "template": {"metadata": {"labels": {"app": app, "version": version}},
                              "spec": {"containers": [{"name": app, "image": f"istio/examples-bookinfo-{name}:1.20.3"}]}}},
        "status": {"readyReplicas": ready, "availableReplicas": ready, "updatedReplicas": replicas},
    }


def replicaset(dep_name, hash_):
    return {"metadata": {"name": f"{dep_name}-{hash_}", "namespace": NS,
                         "annotations": {"deployment.kubernetes.io/revision": "2"},
                         "ownerReferences": [{"kind": "Deployment", "name": dep_name}]},
            "spec": {"replicas": 1}, "status": {"readyReplicas": 1}}


def pod(dep_name, hash_, pid, app, version, ready=True, restarts=0, waiting=None, phase="Running"):
    app_status = {"name": app, "ready": ready, "restartCount": restarts,
                  "state": {"waiting": {"reason": waiting}} if waiting else {"running": {"startedAt": "x"}}}
    return {
        "metadata": {"name": f"{dep_name}-{hash_}-{pid}", "namespace": NS,
                     "labels": {"app": app, "version": version, "pod-template-hash": hash_},
                     "ownerReferences": [{"kind": "ReplicaSet", "name": f"{dep_name}-{hash_}"}],
                     "creationTimestamp": "2026-11-20T08:00:00Z"},
        "spec": {"nodeName": "desktop-worker", "containers": [
            {"name": app, "image": f"istio/examples-bookinfo-{dep_name}:1.20.3",
             "readinessProbe": None, "resources": {}},
            {"name": "istio-proxy", "image": "istio/proxyv2:1.29.1",
             "readinessProbe": {"httpGet": {"path": "/healthz/ready", "port": 15021}},
             "resources": {"requests": {"cpu": "10m", "memory": "40Mi"}}}]},
        "status": {"phase": phase, "podIP": "10.244.1.10",
                   "conditions": [{"type": "Ready", "status": "True" if ready else "False"}],
                   "containerStatuses": [app_status,
                                         {"name": "istio-proxy", "ready": True, "restartCount": 0,
                                          "state": {"running": {}}}]},
    }


def service(name, port=9080):
    return {"metadata": {"name": name, "namespace": NS, "labels": {"app": name, "service": name},
                         "creationTimestamp": "2026-10-13T08:00:00Z"},
            "spec": {"type": "ClusterIP", "clusterIP": f"10.96.0.{len(name)}", "selector": {"app": name},
                     "ports": [{"name": "http", "port": port, "targetPort": port, "protocol": "TCP"}]}}


WORKLOADS = [  # deployment, app, version, rs-hash, pod-id
    ("productpage-v1", "productpage", "v1", "544855df4c", "njtnf"),
    ("details-v1", "details", "v1", "55cd58fc6f", "f4w2s"),
    ("ratings-v1", "ratings", "v1", "7ffd45d9df", "rg9sp"),
    ("reviews-v1", "reviews", "v1", "847664ccd7", "mfjkw"),
    ("reviews-v2", "reviews", "v2", "6dfdd6c5b9", "qdbsd"),
    ("reviews-v3", "reviews", "v3", "64586bf659", "gq9gj"),
]


def bookinfo_snapshot(broken_ratings=False):
    pods = []
    for dep, app, ver, h, pid in WORKLOADS:
        if broken_ratings and app == "ratings":
            pods.append(pod(dep, h, pid, app, ver, ready=False, restarts=79, waiting="CrashLoopBackOff"))
        else:
            pods.append(pod(dep, h, pid, app, ver, restarts=21 if app == "productpage" else 3))
    deps = [deployment(d, a, v, ready=0 if (broken_ratings and a == "ratings") else 1)
            for d, a, v, _, _ in WORKLOADS]
    return {
        "namespace": NS,
        "services": [service(s) for s in ("details", "productpage", "ratings", "reviews")],
        "deployments": deps,
        "replicasets": [replicaset(d, h) for d, _, _, h, _ in WORKLOADS],
        "pods": pods,
    }


def pod_names():
    return [f"{d}-{h}-{p}" for d, _, _, h, p in WORKLOADS]


class FakeK8s:
    def __init__(self, snapshot=None, events=None, istio=None, chaos=None, nodes=None):
        self._snap = snapshot or bookinfo_snapshot()
        self._events = events or []
        self._istio = istio or {"installed": False, "items": []}
        self._chaos = chaos or {"installed": True, "items": []}
        self._nodes = nodes or [{"status": {"allocatable": {"cpu": "4", "memory": "8Gi"},
                                            "conditions": [{"type": "Ready", "status": "True"}]}}]
        self.active_context = "docker-desktop"
        self.server = "https://127.0.0.1:6443"

    def version(self):
        return {"gitVersion": "v1.36.1"}

    def snapshot(self, ns):
        return self._snap

    def list_events(self, ns):
        return self._events

    def list_nodes(self):
        return self._nodes

    def istio_resources(self, ns):
        return self._istio

    def chaos_experiments(self, ns):
        return self._chaos


class FakeProm:
    """Answers instant queries from a {pod: cpu} / {pod: mem} table. `missing` pods get no sample.
    `down=True` simulates an unreachable Prometheus."""

    def __init__(self, cpu=None, mem=None, missing=(), down=False, empty=False):
        names = pod_names()
        self.cpu = cpu if cpu is not None else {n: 0.01 for n in names}
        self.mem = mem if mem is not None else {n: 150.0 for n in names}
        self.missing, self.down, self.empty = set(missing), down, empty
        self.queries = []

    def _fail(self):
        from app.errors import PrometheusUnavailable
        if self.down:
            raise PrometheusUnavailable("Cannot reach Prometheus at http://127.0.0.1:9091")

    def buildinfo(self):
        self._fail()
        return {"version": "3.5.0"}

    def query(self, q):
        self._fail()
        self.queries.append(q)
        if self.empty or "istio_requests_total" in q:
            return []
        if "kube_pod_container_status_restarts_total" in q:
            return [{"labels": {"pod": p, "container": "app"}, "value": 3.0} for p in self.cpu]
        table = self.cpu if "container_cpu_usage_seconds_total" in q else self.mem
        by_container = "container)" in q
        out = []
        for pod_name, v in table.items():
            if pod_name in self.missing:
                continue
            if 'pod=~"' in q:
                import re
                rx = q.split('pod=~"')[1].split('"')[0].replace("\\\\", "\\")
                if not re.fullmatch(rx, pod_name):
                    continue
            labels = {"pod": pod_name}
            if by_container:
                labels["container"] = pod_name.split("-")[0]
            out.append({"labels": labels, "value": v, "timestamp": "2026-11-23T13:00:00Z"})
        return out

    def query_range(self, q, start, end, step):
        self._fail()
        return [{"labels": {"pod": s["labels"]["pod"]},
                 "points": [{"t": "2026-11-23T13:00:00Z", "v": s["value"]},
                            {"t": "2026-11-23T13:00:15Z", "v": None}]} for s in self.query(q)]


def settings(**over):
    base = dict(k8s_namespace=NS, k8s_context="docker-desktop", prometheus_url="http://127.0.0.1:9091",
                prometheus_rate_window="2m", cpu_threshold_cores=0.1, memory_threshold_mib=400.0,
                llm_configured=False)
    base.update(over)
    return SimpleNamespace(**base)
