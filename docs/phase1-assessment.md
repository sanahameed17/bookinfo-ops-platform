# Phase 1 – Assessment of the existing environment and code

Sources inspected: the uploaded project archive `ASE.zip` (Lab 2 tools, Lab 3 agent `lab3-ops-agent/`, evidence
files) and the Lab 1–3 report (82 pages). The live cluster state still has to be confirmed with
`scripts/inspect-env.ps1` (see the end of this document).

## 1. Environment (from the Lab 1–3 report)

| Item | Found | Consequence for this project |
|---|---|---|
| Kubernetes | Docker Desktop built-in Kubernetes, kind provisioner, 1 control plane + 4 workers, v1.36.1 | **Context is `docker-desktop`, not `kind-bookinfo-lab`** (as the original instruction assumed). Default `K8S_CONTEXT=docker-desktop`. |
| Bookinfo | 1.20.3 in namespace `bookinfo`, 4 Services, 6 Deployments, pods 2/2 (app + Envoy) | Discovered dynamically; nothing is redeployed. |
| Istio | 1.29.1 (demo profile), DestinationRules v1/v2/v3, reviews VirtualService 20:40:40, gateway VirtualService in namespace `default` | Istio resources are read cluster-wide so the gateway route is found. |
| Prometheus | kube-prometheus-stack, Helm release `prometheus-operator`, service `prometheus-operator-kube-p-prometheus`, port-forward on **9091** | Default `PROMETHEUS_URL=http://127.0.0.1:9091`. |
| kube-state-metrics | Present (Lab 2 restart query worked) | Used for restarts; the Kubernetes API is used as a second source. |
| Jaeger | Istio add-on in `istio-system` (UI 16686) | Optional source of service dependencies. |
| Grafana, Chaos Mesh 2.8.5, Kuboard | Installed | Not needed. The dashboard warns if Chaos Mesh objects still exist in `bookinfo`. |
| Windows proxy | Clash on 127.0.0.1:10090 intercepted localhost requests in Lab 2 | The backend ignores the system proxy for Prometheus and Jaeger (`trust_env=False`). |
| Restarts | ratings-v1 79, productpage 21, others 6–20 (Lab 2) | Shown as they are; this is real data, not a bug. |
| Requests/limits | Not set in Bookinfo (Grafana showed "No data") | Shown as "not set"; utilisation is given relative to node capacity. |

## 2. Existing code and what is reused

| Lab 3 / Lab 2 component | Reused? | Where in this project |
|---|---|---|
| `core/helper/output_parser.py` (DeepSeek DSML parser) | **Yes, unchanged** | `backend/app/agent/output_parser.py` |
| `core/helper/loop_guard.py` | **Yes** (no exempt tools) | `backend/app/agent/loop_guard.py` |
| `core/agent_builder.py` (initialize_agent STRUCTURED_CHAT, handle_parsing_errors, tool error handling, clean_final_answer) | **Adapted** | `backend/app/agent/runner.py` |
| `core/helper/llm_util.py` (key/URL/model from env, timeout) | **Adapted**; `OPENAI_API_KEY`/`OPENAI_BASE_URL`/`MODEL_NAME` still accepted | `backend/app/config.py`, `runner.py` |
| `ServiceStatus` structured output (LLM fills in health) | **Replaced** by deterministic status (requirement: no LLM for status) | `backend/app/services/status.py` |
| Lab 2 PromQL (`bookinfo_monitor_v2.py`, `prom_range_export.py`) | **Yes**, as the query family. Units are now cores/MiB and missing pods are no longer turned into 0 | `backend/app/services/metrics.py` |
| Lab 3 Docker/kubectl-apply/file/exec tools | **No.** They are write tools, and the new agent must be read-only | – |
| Namespace guard `lab3-*` | **No.** The new agent reads `bookinfo` and writes nothing | – |
| `vue-paper-dashboard` | **No.** It is a Creative Tim template deployed by the agent, not a Bookinfo dashboard | – |

## 3. What was missing (now built)

1. FastAPI backend with Kubernetes discovery (Service → Deployment → ReplicaSet → Pod via selectors and owner references).
2. Prometheus client with timeouts, typed errors, empty-result handling and no zero-filling.
3. React dashboard with clickable service cards and `/services/{name}` detail pages, plus 6 more pages.
4. Read-only agent tools for Kubernetes and Prometheus, `POST /api/chat`, and evidence of tool use.
5. Deterministic anomaly status, Docker Compose, tests and documentation.

## 4. Security notes

* `lab3-ops-agent/.env` (with the DeepSeek and Serper keys) was inside the uploaded ZIP. It was not tracked by Git,
  but if the ZIP was shared anywhere, rotate both keys.
* This project keeps secrets only in `.env` (git-ignored). `/api/config` returns no secrets, and LLM error messages are
  scrubbed of the key.

## 5. Still to confirm on the live cluster

Run `scripts\inspect-env.ps1` and check:
- the current context is `docker-desktop` and all Bookinfo pods are 2/2 Running;
- no Chaos Mesh experiment is still present in `bookinfo` (`kubectl get networkchaos,podchaos,stresschaos -n bookinfo`);
- Prometheus answers on 127.0.0.1:9091 and `kube_pod_container_status_restarts_total` returns data;
- whether `istio_requests_total` exists in Prometheus (otherwise dependencies come from Jaeger).
