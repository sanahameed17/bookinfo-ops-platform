# Deployment and set-up (Windows 11 + Docker Desktop)

Kubernetes, Bookinfo, Istio, Prometheus and Jaeger are **already installed** from Labs 1–3 and are not touched.
Only the two new components run here: the backend and the frontend.

## 1. Prerequisites

| Check | Command | Expected |
|---|---|---|
| Kubernetes context | `kubectl config current-context` | `docker-desktop` (change it with `kubectl config use-context docker-desktop`) |
| Bookinfo | `kubectl get pods -n bookinfo` | 6 pods, `2/2 Running` |
| Prometheus service | `kubectl get svc -n monitoring prometheus-operator-kube-p-prometheus` | exists |
| No leftover chaos | `kubectl get networkchaos,podchaos,stresschaos -n bookinfo` | `No resources found` (or remove the old experiment yourself) |
| Python | `python --version` | 3.11.x |
| Node.js | `node --version` | v20 or newer |

## 2. Configuration (.env)

```powershell
Copy-Item .env.example .env
notepad .env
```
The backend reads `.env` from the project folder (or from `backend/`). Only the backend uses it; the frontend never
receives a secret. Lab 3 variable names (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MODEL_NAME`) are also accepted.

## 3. Local development (recommended)

```powershell
.\scripts\start-port-forwards.ps1        # Prometheus :9091, Jaeger :16686 (minimized windows)

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1             # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# second window
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

**How the backend gets Kubernetes credentials locally:** it reads your normal kubeconfig (`%USERPROFILE%\.kube\config`)
with the `docker-desktop` context, exactly as `kubectl` does. Nothing is copied, and the browser never sees it.

## 4. Docker Compose

```powershell
.\scripts\start-port-forwards.ps1 -ListenAll
.\scripts\make-docker-kubeconfig.ps1
.\scripts\prepare-docker-build.ps1      # builds the React app + downloads Linux wheels (offline docker build)
docker compose up --build -d
docker compose logs -f backend
```
Dashboard: http://localhost:8080 · API docs: http://localhost:8000/docs · Stop with `docker compose down`.

**How the container gets Kubernetes credentials:** `make-docker-kubeconfig.ps1` writes `.kube-docker\config`, a
minified kubeconfig for the `docker-desktop` context only. Its server address is changed from `127.0.0.1` to
`host.docker.internal`, and `tls-server-name` keeps certificate checking on. `compose.yaml` mounts the file
**read-only into the backend container only**. The folder is in `.gitignore`. The frontend container has no
credentials and no API key.

**How the container reaches Prometheus:** inside a container, `127.0.0.1` is the container itself, so compose sets
`PROMETHEUS_URL=http://host.docker.internal:9091`. `-ListenAll` makes the port-forward listen on all interfaces, in
case Docker Desktop cannot reach the host's loopback address. Windows Firewall may ask for permission; allow private
networks only.

Docker Hub blocked? Set the proxy in Docker Desktop → Settings → Resources → Proxies (as in Lab 3) before `--build`.

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Header shows "Backend unreachable" | The backend is not running on port 8000, or the Vite proxy is not pointing to it. |
| `KUBERNETES_UNAVAILABLE … context 'docker-desktop' not found` | Set `K8S_CONTEXT` in `.env` to one of the listed contexts. |
| `PROMETHEUS_UNAVAILABLE` | The port-forward window was closed. Run `.\scripts\start-port-forwards.ps1` again. |
| Prometheus works in the browser but not in the backend | Clash/system proxy. Keep `PROMETHEUS_USE_SYSTEM_PROXY=false`. |
| Docker backend: TLS / certificate error to the API server | Re-run `make-docker-kubeconfig.ps1`. If it still fails, run the backend natively (section 3). The dashboard is identical. |
| Docker backend: Prometheus timeout | Start the port-forwards with `-ListenAll`. |
| CPU/memory "—" for one pod | That pod has no sample yet (just started) → `metrics_unavailable`. This is intentional: it is not shown as 0. |
| "Dependency information unavailable" | Start the Jaeger port-forward and open the product page a few times so traces exist. |
| AI agent 503 `LLM_NOT_CONFIGURED` | Put `LLM_API_KEY` in `.env` and restart the backend. |
| AI agent 502 `LLM_API_ERROR` | Wrong key, model or base URL, quota exhausted, or the network is blocked. The message says which. |
| `npm install` very slow | `npm config set registry https://registry.npmmirror.com` |
| `pip install` very slow | `pip install -r requirements-dev.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
