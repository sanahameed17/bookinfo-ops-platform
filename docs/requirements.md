# Requirements matrix

Status legend: **Verified-S** = verified by automated tests or checks in the development sandbox;
**To verify** = implemented but not yet run in the target environment.

**Update 2026-11-24:** on the Windows machine, backend pytest with live tests passed (84/84, second run) and frontend vitest
passed (9/9). R1–R26 were also confirmed manually in the browser against the live cluster (see [testing.md](testing.md)
sections 3–4). R27 (Docker Compose) was confirmed on 2026-11-24: both containers running, backend healthy.

| # | Requirement | Implementation | Status |
|---|---|---|---|
| R1 | Every Bookinfo microservice on the main dashboard | `OverviewPage` → "Microservices" card grid from `GET /api/services` | Verified-S (render check); To verify (live) |
| R2 | Click a service → dedicated detail page | `ServiceCard` links to `/services/:name` → `ServiceDetailPage` | Verified-S (code); vitest `ServiceCard.test.jsx` to run |
| R3 | Real data from Kubernetes and Prometheus, no mock-up | `k8s_client.py`, `prometheus_client.py`; no data in the frontend | To verify (live tests) |
| R4 | 4 logical services; reviews v1/v2/v3 are versions, not services | `discovery.py` selector + ownerReferences | Verified-S (`test_discovery.py`) |
| R5 | No hard-coded pod names | discovery + pod regex from Deployments | Verified-S |
| R6 | Header: name/logo, context, namespace, Prometheus status, last updated, refresh | `Layout.jsx` | Verified-S (render) |
| R7 | Overview cards (8 figures) from real APIs | `GET /api/cluster/overview` → `OverviewStats` | Verified-S (`test_platform.py`) |
| R8 | Service card fields (health, replicas, pods, CPU, memory, restarts, versions, updated) | `ServiceCard.jsx` | Verified-S |
| R9 | Resource monitoring with history charts, 5/15/60 min | `MetricChart`, `/api/metrics/*`, `RANGE_STEPS` | Verified-S (backend); To verify (charts in browser) |
| R10 | Detail page A–E (overview, workloads, metrics, diagnostics, related) | `ServiceDetailPage.jsx`, `GET /api/services/{name}` | Verified-S (render on real JSON) |
| R11 | Container-level metrics, requests/limits, probes | `current_by_container`, `summarize_pod` | Verified-S |
| R12 | CrashLoopBackOff / ImagePullBackOff / pending detected | `summarize_pod`, diagnostics | Verified-S (`broken_ratings` tests) |
| R13 | Missing metrics clearly identified, never 0 | `prom_results`, `attach_metrics`, `Value` component | Verified-S |
| R14 | Dependencies only from evidence, otherwise explained | `topology.py` (Istio metrics → Jaeger → "unavailable") | Verified-S |
| R15 | Istio routing shown when present | `istio_for_service` | Verified-S (`test_topology.py`) |
| R16 | Read-only discovery of namespaces, services, deployments, RS, pods, nodes, events, Istio | `k8s_client.py` (list only) | Verified-S (no write calls, test) |
| R17 | Configurable namespace (default bookinfo) | `K8S_NAMESPACE` | Verified-S |
| R18 | PromQL for CPU, memory, pod/container, restarts, availability | `metrics.py` | Verified-S (queries); To verify (live) |
| R19 | Timeouts, empty results, unavailable metrics, UTC ISO timestamps, meaningful errors | `prometheus_client.py`, `prom_results.py`, `errors.py` | Verified-S |
| R20 | Cores and MiB; no LLM for metrics | `metrics.py` | Verified-S |
| R21 | FastAPI with routers, schemas, config, error handling, OpenAPI, CORS, logging | `app/` | Schemas Verified-S; API tests to run (FastAPI not installable in sandbox) |
| R22 | Agent reuses Lab 3 safely | parser + LoopGuard reused, write tools dropped | Verified-S (code review, tool tests) |
| R23 | Agent uses real tools, shows evidence, handles LLM errors, key in env, configurable provider | `runner.py`, `tool_impls.py` | Tool tests Verified-S; LangChain tests to run; real LLM To verify |
| R24 | Agent read-only | tools only call PlatformService reads | Verified-S |
| R25 | Deterministic status with thresholds from env; 4 states; offending pod and metric | `status.py` | Verified-S |
| R26 | 8 frontend pages, sidebar, responsive, skeletons, empty/error states, accessible | `src/pages`, `ui.jsx` | Verified-S (render); To verify (visual) |
| R27 | Dockerfiles, compose, .env.example, .gitignore; secrets not in frontend | root + `backend/`, `frontend/`, offline build script | Verified (compose running, backend healthy) |
| R28 | Tests incl. failure cases, real test report | `backend/tests`, `frontend/tests`, `docs/testing.md` | Partly run (see testing.md) |
| R29 | Documentation set | `README.md`, `docs/` | Done |
