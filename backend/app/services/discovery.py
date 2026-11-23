"""
Service discovery - pure functions on plain Kubernetes JSON (no cluster needed to test).

How objects are linked (no names are hard-coded):
  Service  --(spec.selector ⊆ pod labels)-->              Pods
  Service  --(spec.selector ⊆ deployment template labels)--> Deployments
  Pod      --(ownerReferences: ReplicaSet)-->              ReplicaSet
  ReplicaSet --(ownerReferences: Deployment)-->            Deployment
  Version  = the pod/deployment label "version" (v1, v2, v3), falling back to the deployment name

So the logical service "reviews" is ONE Kubernetes Service with THREE Deployments
(reviews-v1/v2/v3), each with its own ReplicaSet(s) and Pod(s).
"""
from typing import Any

WAITING_PROBLEMS = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError",
                    "CreateContainerError", "InvalidImageName", "RunContainerError"}
SIDECAR_NAMES = {"istio-proxy"}


def labels_match(selector: dict | None, labels: dict | None) -> bool:
    if not selector:
        return False
    labels = labels or {}
    return all(labels.get(k) == v for k, v in selector.items())


def _meta(obj: dict) -> dict:
    return obj.get("metadata") or {}


def _owner(obj: dict, kind: str) -> str | None:
    for ref in _meta(obj).get("ownerReferences") or []:
        if ref.get("kind") == kind:
            return ref.get("name")
    return None


def _probe_summary(probe: dict | None) -> dict:
    if not probe:
        return {"configured": False}
    if "httpGet" in probe:
        h = probe["httpGet"]
        how = f"HTTP GET {h.get('path', '/')} :{h.get('port')}"
    elif "tcpSocket" in probe:
        how = f"TCP :{probe['tcpSocket'].get('port')}"
    elif "exec" in probe:
        how = "exec: " + " ".join(probe["exec"].get("command", []))[:80]
    elif "grpc" in probe:
        how = f"gRPC :{probe['grpc'].get('port')}"
    else:
        how = "configured"
    return {"configured": True, "handler": how, "period_seconds": probe.get("periodSeconds"),
            "failure_threshold": probe.get("failureThreshold")}


def _container_state(status: dict | None) -> tuple[str, str | None, str | None]:
    """-> (state, reason, message)"""
    state = (status or {}).get("state") or {}
    for key in ("running", "waiting", "terminated"):
        if key in state and state[key] is not None:
            return key, state[key].get("reason"), state[key].get("message")
    return "unknown", None, None


def summarize_pod(pod: dict) -> dict:
    meta, spec, st = _meta(pod), pod.get("spec") or {}, pod.get("status") or {}
    statuses = {c.get("name"): c for c in (st.get("containerStatuses") or []) + (st.get("initContainerStatuses") or [])}
    containers = []
    problems: list[str] = []
    # Native sidecars (Kubernetes >= 1.29, used by Istio 1.29 for istio-proxy) are initContainers with
    # restartPolicy: Always. They run for the pod's whole life, so they are listed and counted too.
    native_sidecars = [c for c in spec.get("initContainers") or [] if c.get("restartPolicy") == "Always"]
    for c in (spec.get("containers") or []) + native_sidecars:
        cs = statuses.get(c.get("name"))
        state, reason, message = _container_state(cs)
        last_term = (((cs or {}).get("lastState") or {}).get("terminated") or {})
        res = c.get("resources") or {}
        containers.append({
            "name": c.get("name"),
            "image": c.get("image"),
            "is_sidecar": c.get("name") in SIDECAR_NAMES or c.get("restartPolicy") == "Always",
            "ready": bool((cs or {}).get("ready")),
            "restart_count": int((cs or {}).get("restartCount") or 0),
            "state": state,
            "state_reason": reason,
            "state_message": (message or "")[:300] or None,
            "last_terminated_reason": last_term.get("reason"),
            "last_terminated_at": last_term.get("finishedAt"),
            "requests": res.get("requests") or {},
            "limits": res.get("limits") or {},
            "readiness_probe": _probe_summary(c.get("readinessProbe")),
            "liveness_probe": _probe_summary(c.get("livenessProbe")),
        })
        if reason in WAITING_PROBLEMS:
            problems.append(f"{c.get('name')}: {reason}")

    conditions = {c.get("type"): c.get("status") for c in st.get("conditions") or []}
    phase = st.get("phase", "Unknown")
    ready = conditions.get("Ready") == "True"
    terminating = bool(meta.get("deletionTimestamp"))
    if phase in ("Pending", "Failed", "Unknown"):
        problems.append(f"pod phase {phase}")
    elif phase == "Running" and not ready and not terminating:
        not_ready = [c["name"] for c in containers if not c["ready"]]
        problems.append("not ready" + (f" ({', '.join(not_ready)})" if not_ready else ""))

    rs = _owner(pod, "ReplicaSet")
    labels = meta.get("labels") or {}
    return {
        "name": meta.get("name"),
        "namespace": meta.get("namespace"),
        "phase": phase,
        "ready": ready,
        "terminating": terminating,
        "ready_containers": sum(1 for c in containers if c["ready"]),
        "total_containers": len(containers),
        "restart_count": sum(c["restart_count"] for c in containers),
        "pod_ip": st.get("podIP"),
        "node_name": spec.get("nodeName"),
        "start_time": st.get("startTime"),
        "created_at": meta.get("creationTimestamp"),
        "labels": labels,
        "version": labels.get("version"),
        "app": labels.get("app"),
        "replicaset": rs,
        "deployment": None,  # filled in by link_pods()
        "containers": containers,
        "problems": problems,
        "healthy": phase == "Running" and ready and not problems,
    }


def summarize_deployment(dep: dict) -> dict:
    meta, spec, st = _meta(dep), dep.get("spec") or {}, dep.get("status") or {}
    tpl_labels = ((spec.get("template") or {}).get("metadata") or {}).get("labels") or {}
    containers = ((spec.get("template") or {}).get("spec") or {}).get("containers") or []
    return {
        "name": meta.get("name"),
        "version": tpl_labels.get("version") or meta.get("name"),
        "labels": tpl_labels,
        "desired_replicas": spec.get("replicas", 1) if spec.get("replicas") is not None else 1,
        "ready_replicas": st.get("readyReplicas") or 0,
        "available_replicas": st.get("availableReplicas") or 0,
        "updated_replicas": st.get("updatedReplicas") or 0,
        "unavailable_replicas": st.get("unavailableReplicas") or 0,
        "images": [c.get("image") for c in containers],
        "containers": [c.get("name") for c in containers],
        "strategy": (spec.get("strategy") or {}).get("type"),
        "created_at": meta.get("creationTimestamp"),
        "conditions": [{"type": c.get("type"), "status": c.get("status"), "reason": c.get("reason"),
                        "message": c.get("message")} for c in st.get("conditions") or []],
    }


def summarize_replicaset(rs: dict) -> dict:
    meta, spec, st = _meta(rs), rs.get("spec") or {}, rs.get("status") or {}
    return {
        "name": meta.get("name"),
        "deployment": _owner(rs, "Deployment"),
        "revision": (meta.get("annotations") or {}).get("deployment.kubernetes.io/revision"),
        "desired_replicas": spec.get("replicas") or 0,
        "ready_replicas": st.get("readyReplicas") or 0,
        "created_at": meta.get("creationTimestamp"),
    }


def summarize_service_object(svc: dict) -> dict:
    meta, spec = _meta(svc), svc.get("spec") or {}
    return {
        "name": meta.get("name"),
        "namespace": meta.get("namespace"),
        "type": spec.get("type", "ClusterIP"),
        "cluster_ip": spec.get("clusterIP"),
        "selector": spec.get("selector") or {},
        "ports": [{"name": p.get("name"), "port": p.get("port"), "target_port": p.get("targetPort"),
                   "protocol": p.get("protocol", "TCP"), "node_port": p.get("nodePort")}
                  for p in spec.get("ports") or []],
        "labels": meta.get("labels") or {},
        "created_at": meta.get("creationTimestamp"),
    }


def classify_health(deployments: list[dict], pods: list[dict], has_selector: bool) -> tuple[str, str]:
    """Kubernetes-only health of a logical service -> (Healthy|Degraded|Down|Unknown, reason)."""
    if not has_selector:
        return "Unknown", "Service has no selector, workloads cannot be linked"
    live = [p for p in pods if not p["terminating"]]
    if not live:
        return "Down", "No pods match the service selector"
    ready = [p for p in live if p["healthy"]]
    desired = sum(d["desired_replicas"] for d in deployments)
    ready_rep = sum(d["ready_replicas"] for d in deployments)
    problems = [f"{p['name']}: {', '.join(p['problems'])}" for p in live if p["problems"]]
    if not ready:
        return "Down", problems[0] if problems else "No pod is ready"
    if problems or (deployments and ready_rep < desired):
        return "Degraded", problems[0] if problems else f"{ready_rep}/{desired} replicas ready"
    return "Healthy", f"{len(ready)}/{len(live)} pods ready"


def link_pods(snapshot: dict) -> list[dict]:
    rs_to_dep = {_meta(rs).get("name"): _owner(rs, "Deployment") for rs in snapshot.get("replicasets", [])}
    pods = [summarize_pod(p) for p in snapshot.get("pods", [])]
    for p in pods:
        p["deployment"] = rs_to_dep.get(p["replicaset"])
    return pods


def build_service_view(svc: dict, snapshot: dict, pods: list[dict] | None = None) -> dict:
    """Everything Kubernetes knows about one logical service."""
    service = summarize_service_object(svc)
    selector = service["selector"]
    pods = pods if pods is not None else link_pods(snapshot)
    my_pods = [p for p in pods if labels_match(selector, p["labels"])]

    deployments = []
    for dep in snapshot.get("deployments", []):
        d = summarize_deployment(dep)
        if labels_match(selector, d["labels"]):
            deployments.append(d)
    dep_names = {d["name"] for d in deployments}
    replicasets = [summarize_replicaset(rs) for rs in snapshot.get("replicasets", [])
                   if _owner(rs, "Deployment") in dep_names]
    for d in deployments:
        d["replicasets"] = [r for r in replicasets if r["deployment"] == d["name"]]
        d["pods"] = [p["name"] for p in my_pods if p["deployment"] == d["name"]]

    versions = sorted({d["version"] for d in deployments} | {p["version"] for p in my_pods if p["version"]})
    health, reason = classify_health(deployments, my_pods, bool(selector))
    return {
        "service": service,
        "health": health,
        "health_reason": reason,
        "deployments": sorted(deployments, key=lambda d: d["name"]),
        "replicasets": replicasets,
        "pods": sorted(my_pods, key=lambda p: p["name"]),
        "versions": versions,
        "desired_replicas": sum(d["desired_replicas"] for d in deployments),
        "ready_replicas": sum(d["ready_replicas"] for d in deployments),
        "restart_count": sum(p["restart_count"] for p in my_pods),
    }


def build_inventory(snapshot: dict) -> list[dict]:
    pods = link_pods(snapshot)
    views = [build_service_view(s, snapshot, pods) for s in snapshot.get("services", [])]
    return sorted(views, key=lambda v: v["service"]["name"])


def find_service(snapshot: dict, name: str) -> dict | None:
    for s in snapshot.get("services", []):
        if _meta(s).get("name") == name:
            return build_service_view(s, snapshot)
    return None


def unlinked_pods(snapshot: dict) -> list[dict]:
    """Pods that no Service selects (e.g. a test pod) - shown in the Pods explorer."""
    selectors = [(s.get("spec") or {}).get("selector") for s in snapshot.get("services", [])]
    return [p for p in link_pods(snapshot) if not any(labels_match(sel, p["labels"]) for sel in selectors)]


def summarize_event(ev: dict) -> dict:
    meta, inv = _meta(ev), ev.get("involvedObject") or {}
    return {
        "type": ev.get("type"),
        "reason": ev.get("reason"),
        "message": ev.get("message"),
        "object_kind": inv.get("kind"),
        "object_name": inv.get("name"),
        "count": ev.get("count") or 1,
        "first_seen": ev.get("firstTimestamp") or ev.get("eventTime") or meta.get("creationTimestamp"),
        "last_seen": ev.get("lastTimestamp") or ev.get("eventTime") or meta.get("creationTimestamp"),
        "source": (ev.get("source") or {}).get("component") or ev.get("reportingComponent"),
    }


def events_for(events: list[dict], object_names: set[str]) -> list[dict]:
    out = [summarize_event(e) for e in events]
    if object_names:
        out = [e for e in out if e["object_name"] in object_names]
    return sorted(out, key=lambda e: e["last_seen"] or "", reverse=True)


def parse_quantity(q: Any) -> float | None:
    """Kubernetes quantity -> float (cpu in cores, memory in bytes)."""
    if q is None:
        return None
    s = str(q).strip()
    units = {"m": 1e-3, "n": 1e-9, "u": 1e-6, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12,
             "Ki": 1024, "Mi": 1024 ** 2, "Gi": 1024 ** 3, "Ti": 1024 ** 4}
    for suffix in sorted(units, key=len, reverse=True):
        if s.endswith(suffix):
            try:
                return float(s[: -len(suffix)]) * units[suffix]
            except ValueError:
                return None
    try:
        return float(s)
    except ValueError:
        return None


def cluster_capacity(nodes: list[dict]) -> dict:
    cpu = mem = 0.0
    ready = 0
    for n in nodes:
        alloc = (n.get("status") or {}).get("allocatable") or {}
        cpu += parse_quantity(alloc.get("cpu")) or 0.0
        mem += parse_quantity(alloc.get("memory")) or 0.0
        conds = {c.get("type"): c.get("status") for c in (n.get("status") or {}).get("conditions") or []}
        ready += conds.get("Ready") == "True"
    return {"nodes": len(nodes), "ready_nodes": ready, "allocatable_cpu_cores": round(cpu, 3),
            "allocatable_memory_mib": round(mem / 1048576, 1)}
