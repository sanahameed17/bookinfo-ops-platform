"""
All REST endpoints under /api. Every handler is a plain `def` (FastAPI runs it in a worker
thread), because the Kubernetes client and our Prometheus client are synchronous.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query

from app import schemas
from app.config import get_settings
from app.deps import get_agent_runner, get_platform

router = APIRouter(prefix="/api")

ERRORS = {404: {"model": schemas.ErrorResponse}, 502: {"model": schemas.ErrorResponse},
          503: {"model": schemas.ErrorResponse}}
ServiceName = Path(..., pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", max_length=63,
                   description="Kubernetes Service name, e.g. productpage, details, ratings, reviews")
Minutes = Query(15, description="History window in minutes: 5, 15 or 60")


def _minutes(m: int) -> int:
    from app.errors import PlatformError
    if m not in (5, 15, 60):
        err = PlatformError("minutes must be 5, 15 or 60", {"allowed": [5, 15, 60]})
        err.status_code, err.code = 422, "INVALID_RANGE"
        raise err
    return m


# ------------------------------------------------------------------ system
@router.get("/health", response_model=schemas.HealthResponse, tags=["system"],
            summary="Backend, Kubernetes and Prometheus connectivity")
def health(p=Depends(get_platform)):
    return p.health()


@router.get("/config", response_model=schemas.ConfigResponse, tags=["system"],
            summary="Non-secret runtime configuration (for the Settings page)")
def config():
    return get_settings().public_view()


@router.get("/status", response_model=schemas.StatusResponse, tags=["status"], responses=ERRORS,
            summary="Deterministic anomaly status (no LLM)")
def status(p=Depends(get_platform)):
    return p.status()


# ------------------------------------------------------------------ cluster / namespace
@router.get("/cluster/overview", response_model=schemas.OverviewResponse, tags=["cluster"], responses=ERRORS,
            summary="Totals for the overview cards")
def cluster_overview(p=Depends(get_platform)):
    return p.overview()


@router.get("/pods", response_model=schemas.PodsResponse, tags=["cluster"], responses=ERRORS,
            summary="All pods in the namespace with CPU / memory")
def pods(p=Depends(get_platform)):
    return p.pods()


@router.get("/events", response_model=schemas.EventsResponse, tags=["cluster"], responses=ERRORS,
            summary="Kubernetes events in the namespace, newest first")
def events(p=Depends(get_platform)):
    return p.events()


@router.get("/dependencies", response_model=schemas.DependencyGraph, tags=["cluster"], responses=ERRORS,
            summary="Service-to-service calls from Istio telemetry or Jaeger (if available)")
def dependencies(p=Depends(get_platform)):
    return p.all_edges()


# ------------------------------------------------------------------ services
@router.get("/services", response_model=schemas.ServiceListResponse, tags=["services"], responses=ERRORS,
            summary="Inventory of logical services (dashboard cards)")
def list_services(p=Depends(get_platform)):
    return p.list_services()


@router.get("/services/{service_name}", response_model=schemas.ServiceDetailResponse, tags=["services"],
            responses=ERRORS, summary="Everything about one service (detail page)")
def service_detail(service_name: str = ServiceName, p=Depends(get_platform)):
    return p.service_detail(service_name)


@router.get("/services/{service_name}/workloads", response_model=schemas.WorkloadsResponse,
            tags=["services"], responses=ERRORS)
def service_workloads(service_name: str = ServiceName, p=Depends(get_platform)):
    return p.service_workloads(service_name)


@router.get("/services/{service_name}/pods", response_model=schemas.PodsResponse, tags=["services"],
            responses=ERRORS)
def service_pods(service_name: str = ServiceName, p=Depends(get_platform)):
    return p.service_pods(service_name)


@router.get("/services/{service_name}/metrics/cpu", response_model=schemas.HistoryResponse,
            tags=["services"], responses=ERRORS, summary="CPU history (cores) per pod or container")
def service_cpu(service_name: str = ServiceName, minutes: int = Minutes,
                by: Literal["pod", "container"] = "pod", p=Depends(get_platform)):
    return p.service_history(service_name, "cpu", _minutes(minutes), "pod" if by == "pod" else "pod, container")


@router.get("/services/{service_name}/metrics/memory", response_model=schemas.HistoryResponse,
            tags=["services"], responses=ERRORS, summary="Memory working set history (MiB)")
def service_memory(service_name: str = ServiceName, minutes: int = Minutes,
                   by: Literal["pod", "container"] = "pod", p=Depends(get_platform)):
    return p.service_history(service_name, "memory", _minutes(minutes), "pod" if by == "pod" else "pod, container")


@router.get("/services/{service_name}/events", response_model=schemas.EventsResponse, tags=["services"],
            responses=ERRORS)
def service_events(service_name: str = ServiceName, p=Depends(get_platform)):
    return p.service_events(service_name)


# ------------------------------------------------------------------ namespace metrics
@router.get("/metrics/cpu", response_model=schemas.HistoryResponse, tags=["metrics"], responses=ERRORS,
            summary="CPU history (cores) of every pod in the namespace")
def metrics_cpu(minutes: int = Minutes, p=Depends(get_platform)):
    return p.namespace_history("cpu", _minutes(minutes))


@router.get("/metrics/memory", response_model=schemas.HistoryResponse, tags=["metrics"], responses=ERRORS,
            summary="Memory working set history (MiB) of every pod in the namespace")
def metrics_memory(minutes: int = Minutes, p=Depends(get_platform)):
    return p.namespace_history("memory", _minutes(minutes))


@router.get("/metrics/restarts", response_model=schemas.RestartsResponse, tags=["metrics"], responses=ERRORS,
            summary="Container restarts from kube-state-metrics and from the Kubernetes API")
def metrics_restarts(p=Depends(get_platform)):
    return p.restarts()


# ------------------------------------------------------------------ AI agent
@router.post("/chat", response_model=schemas.ChatResponse, tags=["agent"], responses=ERRORS,
             summary="Ask the read-only AI OpsAgent a question")
def chat(body: schemas.ChatRequest, runner=Depends(get_agent_runner)):
    return runner.ask(body.message, [m.model_dump() for m in body.history])
