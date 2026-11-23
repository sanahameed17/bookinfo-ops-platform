# Testing

**Rule: a test is reported as passed only if it was actually executed and passed.** The raw outputs are in
[`test-results/`](test-results/).

## 1. Test suites

| Suite | File(s) | Needs | What it covers |
|---|---|---|---|
| Discovery unit tests | `backend/tests/unit/test_discovery.py` (12) | Python + pytest | 4 services not 6, reviews v1/v2/v3, Pod→RS→Deployment, ports/selector, containers/probes/resources, CrashLoopBackOff → Down, restarts, no selector, unknown service, quantities, events |
| Metrics & status | `backend/tests/unit/test_metrics_and_status.py` (19) | Python + pytest | parsing (NaN → null, UTC ISO, empty, error), PromQL units/filters, pod regex, CPU, memory, restarts, **empty metrics**, **missing ≠ 0**, **Prometheus failure**, history ranges, every status state |
| Platform | `backend/tests/unit/test_platform.py` (10) | Python + pytest | overview totals, Prometheus down → no fake numbers, Chaos Mesh warning, cards, detail, 404, Jaeger dependencies, history query, health |
| Topology | `backend/tests/unit/test_topology.py` (5) | Python + pytest | Istio weights 20/40/40, subsets, gateway VS in `default`, Istio-metric dependencies, "unavailable" explanation |
| Agent | `backend/tests/unit/test_agent.py` (13) | pytest; 2 tests need langchain | read-only tools, CPU ranking, reviews v1 vs v3, refuses to guess without Prometheus, restarts, unhealthy pods, loop guard, not configured; **fake-LLM run calling a real tool**; **LLM API error hides key** |
| API | `backend/tests/api/test_api.py` (17 incl. 5 parametrized) | fastapi, httpx, pydantic-settings | every endpoint, 404/422 structured errors, empty metrics, Prometheus failure → 503, crashloop status, no secrets in /api/config, chat 502, chat validation |
| Live integration | `backend/tests/integration/test_live_cluster.py` (8) | your cluster + port-forward, `LIVE_TESTS=1` | Kubernetes connectivity, service/deployment/pod discovery, Prometheus connectivity, CPU/memory/restart metrics, detail |
| Frontend | `frontend/tests/ServiceCard.test.jsx` (3), `apiClient.test.jsx` (6) | npm packages (vitest, jsdom) | **card click → /services/reviews**, missing metrics shown as "—", API errors 503/404/502/unreachable, ErrorState |

## 2. Results already executed (development sandbox, 23 Nov 2026)

The sandbox had Python 3.13 + pytest, Node 22 + esbuild + React, but **no network**, so FastAPI, httpx, the
kubernetes client, LangChain, Vite and vitest could not be installed. Results:

| Suite | Result | Evidence |
|---|---|---|
| Backend unit tests (discovery, metrics, status, platform, topology, agent tools) | **57 passed** | `test-results/backend-pytest-sandbox.txt` |
| Agent fake-LLM tests (2) | skipped – langchain not installed | same file |
| API tests (17 incl. parametrized) | skipped – fastapi not installed | same file |
| Live integration tests (8) | skipped – no cluster in the sandbox | same file |
| Pydantic validation of every API response (normal, Prometheus down, empty, missing, crashloop variants) | **passed** (script check) | described here |
| Frontend: bundle + server-side render of all 8 pages + layout, with real backend JSON, normal and "Prometheus down" | **20/20 rendered** | `test-results/frontend-ssr-smoke-sandbox.txt` |
| Frontend vitest (card navigation, API errors) | **not run yet** | – |

## 3. Run the full suite on your machine

```powershell
# once
cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements-dev.txt; cd ..
cd frontend; npm install; cd ..

# unit + API + frontend
.\scripts\run-tests.ps1
# + live tests (port-forward must be running)
.\scripts\run-tests.ps1 -Live
```
The script writes `docs/test-results/backend-pytest.txt` and `frontend-vitest.txt`. Copy their summary lines into the
table below. Only then do they count as evidence.

| Suite | Result on the Windows machine (Python 3.12.10, Node 26.13.1) | Date / time (UTC+8) |
|---|---|---|
| Frontend vitest (`ServiceCard.test.jsx`, `apiClient.test.jsx`) | **9 passed (2 files)** | 2026-11-24 00:35 |
| Backend pytest, run 1, `LIVE_TESTS=1` | **78 passed, 6 failed.** Failures: `KubernetesUnavailable: Kubernetes API error 403` from the live cluster tests; run took 73 s | 2026-11-24 00:38 |
| Backend pytest, run 2, `LIVE_TESTS=1` (no code change) | **84 passed, 0 failed** in 11.6 s | 2026-11-24 00:43 |

The 403 errors in run 1 were intermittent: the same code passed 5 minutes later, and the dashboard stayed connected.
The cause was not established. Possible causes are the Docker Desktop API endpoint briefly refusing requests, or the
Windows system proxy. It is recorded as a known limitation.

Note: the first version of `scripts/run-tests.ps1` printed "Backend tests: PASSED" for run 1 although tests had failed.
Its output file was also unreadable, because `Tee-Object` writes UTF-16 in Windows PowerShell 5.1. The script was
fixed to use `Out-String | Out-File -Encoding utf8`. The numbers above are from pytest's own summary line.

## 4. Manual acceptance checks (performed on 2026-11-23/24)

| # | Check | Expected | Result |
|---|---|---|---|
| M1 | Open http://localhost:5173 | 8 overview cards with real numbers, 4 service cards | **Passed**: 4 services, 6 deployments, 6 pods, 598 restarts (= `kubectl` sum), 0.059 cores, 933 MiB |
| M2 | Click the `reviews` card | `/services/reviews`; 3 Deployments v1/v2/v3, 3 pods, charts, Istio 20/40/40 | **Passed**: all shown; dependencies productpage → reviews → ratings from Jaeger |
| M3 | Prometheus port-forward stopped | "Prometheus unavailable", CPU/memory "—", pods still listed | covered by automated tests; not yet tried manually |
| M4 | Backend stopped | red "Cannot reach the backend API" | **Observed**: header showed "Backend unreachable" while the backend was restarting |
| M5 | Agent: "Which Bookinfo Pod is using the most CPU?" | names a pod; evidence `get_pod_cpu_usage` | **Passed**: reviews-v2 0.0267 cores, 1 tool call |
| M5b | Agent: "Which Pods have failed readiness checks?" | uses pods + events | **Passed** (after fix): reviews-v1 12×, ratings-v1 7× istio-proxy probe timeouts; tools `get_pods`, `get_pod_events` |
| M6 | Agent with no balance / bad key | structured error, no key | **Passed**: HTTP 502 `LLM_API_ERROR` "402 Insufficient Balance", no key shown |
| M8 | `docker compose up --build` (offline build) | both containers running, dashboard on :8080 | **Passed** (2026-11-24 02:14): `docker compose ps` shows backend `Up (healthy)` and frontend `Up`; the Settings page at :8080 shows Kubernetes connected (v1.36.1) via `https://host.docker.internal:57571` and Prometheus connected (v3.15.0) via `http://host.docker.internal:9091` |
| M7 | Open `/services/nope` | 404 with links to real services | not yet tried manually (covered by API test) |

## 5. Problems found during live testing and fixed

| Problem | Fix |
|---|---|
| Python Kubernetes client used the Clash system proxy (127.0.0.1:10090) → SSL EOF | proxy disabled for local API servers (`k8s_client.py`) |
| Istio 1.29 native sidecars (`initContainers`, `restartPolicy: Always`) not counted → restarts half of `kubectl` | native sidecars included (`discovery.py`), unit test added |
| First dashboard load: concurrent first connections → transient errors | connection lock + 3 retries (`k8s_client.py`) |
| Agent misread "probe configured = false" as a failure and ignored events | unambiguous tool fields, `probe_failures` from events, prompt rule (`tool_impls.py`, `runner.py`) |
| `requirements.txt` upper bounds → pip `ResolutionImpossible` | upper bounds removed |
| `run-tests.ps1` wrong PASS status and UTF-16 output | fixed (see section 3) |
| `npm install` / `pip install` inside `docker build` timed out (no reliable internet in build containers) | offline build: `scripts/prepare-docker-build.ps1` builds the React app and downloads Linux wheels on the host |
| `pip download` on Windows skipped the Linux-only `uvloop` | downloaded explicitly in the prepare script |
| Windows allowed two uvicorn processes on port 8000 → old code kept answering | documented: stop the old backend (Ctrl+C) before starting a new one |
