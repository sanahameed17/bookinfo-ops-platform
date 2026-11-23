"""
Pydantic response / request models. FastAPI uses them to validate every response and to build
the OpenAPI documentation at /docs.

Conventions:
  * CPU in cores, memory in MiB, timestamps UTC ISO 8601 ("...Z").
  * A value that is unknown is null - never 0.
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

HealthState = Literal["Healthy", "Degraded", "Down", "Unknown"]
StatusState = Literal["normal", "anomalous", "prometheus_unavailable", "metrics_unavailable"]
MetricsState = Literal["ok", "metrics_unavailable", "prometheus_unavailable"]


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Meta(Model):
    namespace: str
    generated_at: str
    kubernetes_context: str | None = None
    prometheus_available: bool | None = None
    prometheus_error: str | None = None


class ErrorBody(Model):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(Model):
    error: ErrorBody


# ------------------------------------------------------------------ health / config
class K8sHealth(Model):
    ok: bool
    context: str | None = None
    server: str | None = None
    version: str | None = None
    error: str | None = None
    details: dict[str, Any] | None = None


class PromHealth(Model):
    available: bool
    version: str | None = None
    url: str
    error: str | None = None


class HealthResponse(Model):
    status: Literal["ok", "degraded"]
    kubernetes: K8sHealth
    prometheus: PromHealth
    llm_configured: bool
    generated_at: str


class ConfigResponse(Model):
    namespace: str
    kubernetes_context: str
    kubernetes_in_cluster: bool
    prometheus_url: str
    prometheus_timeout_seconds: float
    prometheus_rate_window: str
    jaeger_url: str
    cpu_threshold_cores: float
    memory_threshold_mib: float
    llm_provider: str
    llm_model: str
    llm_base_url_host: str
    llm_configured: bool


# ------------------------------------------------------------------ status
class Finding(Model):
    pod: str
    service: str | None = None
    deployment: str | None = None
    metric: str
    value: float | None = None
    threshold: float | None = None
    unit: str | None = None
    severity: str
    message: str


class MissingMetric(Model):
    pod: str
    service: str | None = None
    deployment: str | None = None
    metric: str


class Evaluation(Model):
    status: StatusState
    prometheus_available: bool
    prometheus_error: str | None = None
    thresholds: dict[str, float]
    anomalies: list[Finding]
    missing_metrics: list[MissingMetric]
    pods_evaluated: int


class ServiceHealthLine(Model):
    name: str
    health: HealthState
    health_reason: str


class StatusResponse(Evaluation):
    meta: Meta
    services: list[ServiceHealthLine]


# ------------------------------------------------------------------ kubernetes objects
class Probe(Model):
    configured: bool
    handler: str | None = None
    period_seconds: int | None = None
    failure_threshold: int | None = None


class Container(Model):
    name: str
    image: str | None = None
    is_sidecar: bool
    ready: bool
    restart_count: int
    state: str
    state_reason: str | None = None
    state_message: str | None = None
    last_terminated_reason: str | None = None
    last_terminated_at: str | None = None
    requests: dict[str, str] = {}
    limits: dict[str, str] = {}
    readiness_probe: Probe
    liveness_probe: Probe
    cpu_cores: float | None = None
    memory_mib: float | None = None


class Pod(Model):
    name: str
    namespace: str | None = None
    phase: str
    ready: bool
    terminating: bool
    healthy: bool
    ready_containers: int
    total_containers: int
    restart_count: int
    pod_ip: str | None = None
    node_name: str | None = None
    start_time: str | None = None
    created_at: str | None = None
    labels: dict[str, str] = {}
    version: str | None = None
    app: str | None = None
    replicaset: str | None = None
    deployment: str | None = None
    service: str | None = None
    containers: list[Container]
    problems: list[str]
    cpu_cores: float | None = None
    memory_mib: float | None = None
    metrics_state: MetricsState | None = None


class ReplicaSet(Model):
    name: str
    deployment: str | None = None
    revision: str | None = None
    desired_replicas: int
    ready_replicas: int
    created_at: str | None = None


class Deployment(Model):
    name: str
    version: str
    labels: dict[str, str] = {}
    desired_replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int
    unavailable_replicas: int
    images: list[str | None]
    containers: list[str | None]
    strategy: str | None = None
    created_at: str | None = None
    conditions: list[dict[str, Any]] = []
    replicasets: list[ReplicaSet] = []
    pods: list[str] = []


class ServicePort(Model):
    name: str | None = None
    port: int | None = None
    target_port: int | str | None = None
    protocol: str = "TCP"
    node_port: int | None = None


class ServiceObject(Model):
    name: str
    namespace: str | None = None
    type: str
    cluster_ip: str | None = None
    selector: dict[str, str] = {}
    ports: list[ServicePort]
    labels: dict[str, str] = {}
    created_at: str | None = None


class Event(Model):
    type: str | None = None
    reason: str | None = None
    message: str | None = None
    object_kind: str | None = None
    object_name: str | None = None
    count: int = 1
    first_seen: str | None = None
    last_seen: str | None = None
    source: str | None = None


# ------------------------------------------------------------------ services
class ServiceCard(Model):
    name: str
    health: HealthState
    health_reason: str
    status: StatusState
    ready_replicas: int
    desired_replicas: int
    pod_count: int
    ready_pods: int
    versions: list[str]
    version_count: int
    deployments: list[str]
    cpu_cores: float | None = None
    memory_mib: float | None = None
    metrics_state: MetricsState
    restart_count: int
    anomalies: list[Finding]
    updated_at: str


class ServiceListResponse(Model):
    meta: Meta
    services: list[ServiceCard]


class Dependencies(Model):
    available: bool
    source: str | None = None
    note: str | None = None
    calls: list[str] = []
    called_by: list[str] = []
    edges: list[dict[str, Any]] = []


class IstioInfo(Model):
    installed: bool
    virtual_services: list[dict[str, Any]] = []
    destination_rules: list[dict[str, Any]] = []
    gateways: list[dict[str, Any]] = []
    note: str | None = None


class Diagnostics(Model):
    status: Evaluation
    failed_or_pending_pods: list[str]
    crashloop_pods: list[str]
    image_pull_problems: list[str]
    not_ready_pods: list[str]
    warning_events: list[Event]
    resources_configured: bool


class MetricsInfo(Model):
    available: bool
    error: str | None = None
    queries: dict[str, str]
    container_metrics_available: bool


class ServiceDetailResponse(Model):
    meta: Meta
    summary: ServiceCard
    service: ServiceObject
    deployments: list[Deployment]
    replicasets: list[ReplicaSet]
    pods: list[Pod]
    metrics: MetricsInfo
    diagnostics: Diagnostics
    istio: IstioInfo
    dependencies: Dependencies
    events: list[Event]


class WorkloadsResponse(Model):
    meta: Meta
    service: str
    versions: list[str]
    deployments: list[Deployment]
    replicasets: list[ReplicaSet]


class PodsResponse(Model):
    meta: Meta
    service: str | None = None
    pods: list[Pod]


class EventsResponse(Model):
    meta: Meta
    service: str | None = None
    events: list[Event]


# ------------------------------------------------------------------ metrics
class Point(Model):
    t: str
    v: float | None = None


class Series(Model):
    name: str
    labels: dict[str, str]
    points: list[Point]


class HistoryResponse(Model):
    meta: Meta
    service: str | None = None
    metric: Literal["cpu", "memory"]
    unit: Literal["cores", "MiB"]
    minutes: int
    step_seconds: int | None = None
    query: str | None = None
    series: list[Series]
    note: str | None = None


class RestartItem(Model):
    pod: str | None = None
    container: str | None = None
    restarts: int | None = None
    last_terminated_reason: str | None = None


class PromRestarts(Model):
    available: bool
    error: str | None = None
    query: str
    items: list[RestartItem]


class K8sRestarts(Model):
    source: str
    items: list[RestartItem]


class RestartsResponse(Model):
    meta: Meta
    prometheus: PromRestarts
    kubernetes: K8sRestarts


# ------------------------------------------------------------------ overview
class Totals(Model):
    microservices: int
    deployments: int
    pods: int
    running_pods: int
    unhealthy_pods: int
    container_restarts: int
    cpu_cores: float | None = None
    memory_mib: float | None = None
    cpu_percent_of_cluster: float | None = None
    memory_percent_of_cluster: float | None = None


class ClusterCapacity(Model):
    nodes: int
    ready_nodes: int
    allocatable_cpu_cores: float
    allocatable_memory_mib: float


class PromSummary(Model):
    available: bool
    error: str | None = None
    url: str


class ChaosItem(Model):
    kind: str | None = None
    name: str
    paused: bool = False
    created_at: str | None = None


class OverviewResponse(Model):
    meta: Meta
    totals: Totals
    cluster: ClusterCapacity | None = None
    prometheus: PromSummary
    status: StatusState
    anomaly_count: int
    chaos_experiments: list[ChaosItem]
    warnings: list[str]


class DependencyGraph(Model):
    source: str | None = None
    available: bool
    edges: list[dict[str, Any]]
    query: str | None = None
    note: str | None = None


# ------------------------------------------------------------------ chat
class ChatMessage(Model):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(Model):
    message: str = Field(min_length=1, max_length=2000,
                         examples=["Which Bookinfo pod is using the most CPU?"])
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)


class ToolCall(Model):
    tool: str
    input: Any = None
    output_preview: str
    duration_ms: int


class ChatResponse(Model):
    answer: str
    tools_used: list[ToolCall]
    model: str
    duration_ms: int
    generated_at: str
