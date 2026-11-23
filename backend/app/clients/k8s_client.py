"""
READ-ONLY Kubernetes client.

Only list/read/get calls exist in this file - there is deliberately no create, patch, delete,
scale or exec method anywhere in the backend, so neither the dashboard nor the AI agent can
change the cluster.

Kubernetes objects are converted to plain dicts (the same JSON you see with `kubectl get -o json`)
so that the discovery logic in app/services/discovery.py can be unit-tested without a cluster.
"""
import logging
import threading
import time
from typing import Any

from app.errors import KubernetesUnavailable

log = logging.getLogger(__name__)

ISTIO_GROUP = "networking.istio.io"
ISTIO_KINDS = {"virtualservices": "VirtualService", "destinationrules": "DestinationRule",
               "gateways": "Gateway"}
CHAOS_GROUP = "chaos-mesh.org"
CHAOS_PLURALS = ["podchaos", "networkchaos", "stresschaos", "iochaos", "httpchaos",
                 "dnschaos", "timechaos", "schedules", "workflows"]


class K8sClient:
    def __init__(self, context: str = "", in_cluster: bool = False, timeout: float = 10.0,
                 cache_seconds: float = 5.0):
        self.context = context
        self.in_cluster = in_cluster
        self.timeout = timeout
        self.cache_seconds = cache_seconds
        self._lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._api = None
        self.active_context = None
        self.server = None

    # ------------------------------------------------------------------ connection
    def _connect(self):
        if self._api is not None:
            return self._api
        with self._connect_lock:  # the dashboard sends several requests at once on first load
            if self._api is not None:
                return self._api
            return self._connect_locked()

    def _connect_locked(self):
        try:
            from kubernetes import client, config
        except ImportError as e:  # pragma: no cover
            raise KubernetesUnavailable("The 'kubernetes' Python package is not installed") from e
        try:
            if self.in_cluster:
                config.load_incluster_config()
                self.active_context = "in-cluster"
            else:
                contexts, current = config.list_kube_config_contexts()
                names = [c["name"] for c in contexts]
                wanted = self.context or (current or {}).get("name")
                if wanted not in names:
                    raise KubernetesUnavailable(
                        f"kubeconfig context '{wanted}' not found",
                        {"available_contexts": names,
                         "hint": "Set K8S_CONTEXT in .env to one of the available contexts"})
                config.load_kube_config(context=wanted)
                self.active_context = wanted
        except KubernetesUnavailable:
            raise
        except Exception as e:
            raise KubernetesUnavailable(f"Cannot load Kubernetes configuration: {e}") from e

        cfg = client.Configuration.get_default_copy()
        cfg.retries = 3  # Docker Desktop's API endpoint occasionally drops a TLS connection; retry it
        # Clash / Windows system proxy must not be used for a local API server (kubectl skips it too)
        local = ("://127.0.0.1", "://localhost", "://host.docker.internal", "://kubernetes.docker.internal")
        if any(h in (cfg.host or "") for h in local):
            cfg.proxy = None
        api_client = client.ApiClient(cfg)
        self.server = cfg.host
        self._api = {
            "client": api_client,
            "core": client.CoreV1Api(api_client),
            "apps": client.AppsV1Api(api_client),
            "custom": client.CustomObjectsApi(api_client),
            "version": client.VersionApi(api_client),
        }
        log.info("Kubernetes client ready: context=%s server=%s", self.active_context, self.server)
        return self._api

    def _call(self, fn, *args, raw_api_errors: bool = False, **kwargs):
        """Run one API call, convert the result to plain dicts, map errors.
        raw_api_errors=True re-raises HTTP errors (404/403) so the caller can handle optional CRDs."""
        api = self._connect()
        try:
            result = fn(*args, _request_timeout=self.timeout, **kwargs)
        except Exception as e:
            status = getattr(e, "status", None)
            if status is not None:  # ApiException: the server answered with an HTTP error
                if raw_api_errors:
                    raise
                hint = {401: "credentials rejected (kubeconfig expired?)",
                        403: "access forbidden (RBAC: read permission missing)",
                        404: "resource or namespace not found"}.get(status, getattr(e, "reason", ""))
                raise KubernetesUnavailable(f"Kubernetes API error {status}: {hint}",
                                            {"status": status, "context": self.active_context}) from e
            raise KubernetesUnavailable(
                f"Kubernetes API not reachable ({type(e).__name__}). Is the cluster running?",
                {"server": self.server, "context": self.active_context, "reason": str(e)[:300]},
            ) from e
        return api["client"].sanitize_for_serialization(result)

    def _cached(self, key: str, loader):
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < self.cache_seconds:
                return hit[1]
        value = loader()
        with self._lock:
            self._cache[key] = (now, value)
        return value

    # ------------------------------------------------------------------ read operations
    def version(self) -> dict:
        api = self._connect()
        return self._call(api["version"].get_code)

    def list_namespaces(self) -> list[dict]:
        api = self._connect()
        return self._cached("namespaces", lambda: self._call(api["core"].list_namespace)["items"])

    def list_nodes(self) -> list[dict]:
        api = self._connect()
        return self._cached("nodes", lambda: self._call(api["core"].list_node)["items"])

    def snapshot(self, namespace: str) -> dict:
        """All objects the dashboard needs for one namespace, fetched together and cached for a
        few seconds so the many parallel dashboard requests do not hammer the API server."""
        def load():
            api = self._connect()
            core, apps = api["core"], api["apps"]
            return {
                "namespace": namespace,
                "services": self._call(core.list_namespaced_service, namespace)["items"],
                "deployments": self._call(apps.list_namespaced_deployment, namespace)["items"],
                "replicasets": self._call(apps.list_namespaced_replica_set, namespace)["items"],
                "pods": self._call(core.list_namespaced_pod, namespace)["items"],
                "fetched_at": time.time(),
            }
        return self._cached(f"snapshot:{namespace}", load)

    def list_events(self, namespace: str) -> list[dict]:
        api = self._connect()
        return self._cached(f"events:{namespace}",
                            lambda: self._call(api["core"].list_namespaced_event, namespace)["items"])

    def istio_resources(self, namespace: str) -> dict:
        """VirtualServices / DestinationRules / Gateways. Cluster-wide first (the Bookinfo
        gateway VirtualService lives in 'default' in this lab), namespace-only if forbidden."""
        def load():
            api = self._connect()
            custom = api["custom"]
            out: dict[str, Any] = {"installed": False, "items": [], "errors": []}
            for plural, kind in ISTIO_KINDS.items():
                items = None
                for version in ("v1", "v1beta1"):
                    try:
                        items = self._call(custom.list_cluster_custom_object,
                                           ISTIO_GROUP, version, plural, raw_api_errors=True)["items"]
                    except KubernetesUnavailable:
                        raise
                    except Exception as e:
                        status = getattr(e, "status", None)
                        if status == 404:
                            continue
                        if status == 403:
                            try:
                                items = self._call(custom.list_namespaced_custom_object, ISTIO_GROUP,
                                                   version, namespace, plural, raw_api_errors=True)["items"]
                            except Exception as e2:
                                out["errors"].append(f"{kind}: {e2}")
                        else:
                            out["errors"].append(f"{kind}: {e}")
                    break
                if items is not None:
                    out["installed"] = True
                    for it in items:
                        it.setdefault("kind", kind)
                    out["items"].extend(items)
            return out
        return self._cached(f"istio:{namespace}", load)

    def chaos_experiments(self, namespace: str) -> dict:
        """Chaos Mesh objects in the namespace (read-only). A forgotten experiment explains
        'unhealthy' pods, so the dashboard shows them as a warning."""
        def load():
            api = self._connect()
            custom = api["custom"]
            out: dict[str, Any] = {"installed": False, "items": []}
            for plural in CHAOS_PLURALS:
                try:
                    items = self._call(custom.list_namespaced_custom_object, CHAOS_GROUP,
                                       "v1alpha1", namespace, plural, raw_api_errors=True)["items"]
                except KubernetesUnavailable:
                    raise
                except Exception:
                    continue
                out["installed"] = True
                out["items"].extend(items)
            return out
        return self._cached(f"chaos:{namespace}", load)
