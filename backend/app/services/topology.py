"""
Istio routing and service dependencies.

Dependencies are only reported when there is real evidence:
  1. Istio telemetry in Prometheus (istio_requests_total, reporter="destination"), or
  2. the Jaeger dependency API (built from real traces).
If neither source has data the API says so - dependencies are never guessed from names.
"""
from app.services.discovery import _meta


def _short_host(host: str | None, namespace: str) -> str | None:
    if not host:
        return None
    for suffix in (f".{namespace}.svc.cluster.local", f".{namespace}.svc", f".{namespace}"):
        if host.endswith(suffix):
            return host[: -len(suffix)]
    return host


def istio_for_service(istio: dict, service: str, namespace: str) -> dict:
    """VirtualServices / DestinationRules that route to or define subsets for this service."""
    if not istio.get("installed"):
        return {"installed": False, "virtual_services": [], "destination_rules": [], "gateways": [],
                "note": "Istio networking CRDs were not found or are not readable."}
    vs_out, dr_out, gw_names = [], [], set()
    for it in istio.get("items", []):
        kind, meta, spec = it.get("kind"), _meta(it), it.get("spec") or {}
        item_ns = meta.get("namespace") or namespace
        if kind == "VirtualService":
            routes = []
            for http in spec.get("http") or []:
                for r in http.get("route") or []:
                    d = r.get("destination") or {}
                    routes.append({"host": d.get("host"), "short_host": _short_host(d.get("host"), namespace),
                                   "subset": d.get("subset"), "port": (d.get("port") or {}).get("number"),
                                   "weight": r.get("weight"),
                                   "match": http.get("match")})
            hosts = [_short_host(h, namespace) for h in spec.get("hosts") or []]
            if service in hosts or any(r["short_host"] == service for r in routes):
                gw_names.update(spec.get("gateways") or [])
                vs_out.append({"name": meta.get("name"), "namespace": item_ns, "hosts": spec.get("hosts") or [],
                               "gateways": spec.get("gateways") or [], "routes": routes})
        elif kind == "DestinationRule":
            if _short_host(spec.get("host"), namespace) == service:
                dr_out.append({"name": meta.get("name"), "namespace": item_ns, "host": spec.get("host"),
                               "subsets": [{"name": s.get("name"), "labels": s.get("labels") or {}}
                                           for s in spec.get("subsets") or []],
                               "traffic_policy": spec.get("trafficPolicy")})
    gateways = [{"name": _meta(it).get("name"), "namespace": _meta(it).get("namespace"),
                 "servers": (it.get("spec") or {}).get("servers")}
                for it in istio.get("items", [])
                if it.get("kind") == "Gateway" and _meta(it).get("name") in {g.split("/")[-1] for g in gw_names}]
    note = None if (vs_out or dr_out) else \
        "No VirtualService or DestinationRule references this service; Kubernetes default round-robin applies."
    return {"installed": True, "virtual_services": vs_out, "destination_rules": dr_out,
            "gateways": gateways, "note": note}


def edges_from_istio(edge_result: dict, workload_to_service: dict[str, str]) -> list[dict]:
    out = []
    for e in edge_result.get("edges", []):
        src_w = e.get("source_workload") or "unknown"
        src = workload_to_service.get(src_w) or src_w
        dst = e.get("destination_service") or workload_to_service.get(e.get("destination_workload") or "", "?")
        out.append({"source": src, "source_workload": src_w, "target": _short_host(dst, ""),
                    "target_workload": e.get("destination_workload"),
                    "requests_per_second": e.get("requests_per_second")})
    return out


def edges_from_jaeger(deps: list[dict], namespace: str) -> list[dict]:
    """Jaeger names services '<service>.<namespace>' when traced through Istio."""
    def norm(name: str) -> str:
        return name[: -len(f".{namespace}")] if name and name.endswith(f".{namespace}") else name
    return [{"source": norm(d.get("parent")), "target": norm(d.get("child")),
             "call_count": d.get("callCount")} for d in deps if d.get("parent") != d.get("child")]


def dependencies_for(service: str, edges: list[dict]) -> dict:
    calls = sorted({e["target"] for e in edges if e["source"] == service and e["target"] != service})
    called_by = sorted({e["source"] for e in edges if e["target"] == service and e["source"] != service})
    return {"calls": calls, "called_by": called_by,
            "edges": [e for e in edges if service in (e["source"], e["target"])]}
