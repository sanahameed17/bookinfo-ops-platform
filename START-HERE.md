# Yahan se shuru karein (step by step, PowerShell)

Har command project folder (`bookinfo-ops-platform`) ke andar chalani hai. Har step ke baad dekh lein ke
"Expected" wala result aaya hai ya nahi. Agar koi step fail ho to uska error copy karke mujhe bhej dein.

## Step 1 – Cluster check
```powershell
kubectl config use-context docker-desktop
kubectl get pods -n bookinfo
kubectl get networkchaos,podchaos,stresschaos -n bookinfo
```
Expected: 6 pods `2/2 Running`, aur chaos wali command par `No resources found`.

## Step 2 – .env file
```powershell
Copy-Item .env.example .env
notepad .env
```
`LLM_API_KEY=` ke aage apni DeepSeek key likhein (Lab 3 wali `.env` mein `OPENAI_API_KEY` thi, wahi key). Save karke band kar dein.

## Step 3 – Port-forwards (Prometheus + Jaeger)
```powershell
.\scripts\start-port-forwards.ps1
```
Expected: `Prometheus is reachable (version ...)`. Do minimized windows khulengi, unko band **na** karein.
Agar "running scripts is disabled" error aaye: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` chalayein, phir dobara try karein.

## Step 4 – Backend (pehli baar)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```
Browser mein http://127.0.0.1:8000/api/health kholein. Expected: `"kubernetes": {"ok": true ...}` aur `"prometheus": {"available": true ...}`.
API docs: http://127.0.0.1:8000/docs

## Step 5 – Frontend (nayi PowerShell window, pehli baar)
```powershell
cd frontend
npm install
npm run dev
```
Browser: **http://localhost:5173**. Dashboard par 4 service cards dikhne chahiye. Kisi card par click karein, detail page khulega.

## Step 6 – Tests
```powershell
.\scripts\run-tests.ps1 -Live
```
Results `docs\test-results\` mein save honge, aur `docs\testing.md` ki table mein likhne hain.

## Step 7 – Docker (aakhri step, optional)
```powershell
.\scripts\start-port-forwards.ps1 -ListenAll
.\scripts\make-docker-kubeconfig.ps1
docker compose up --build
```
Dashboard: http://localhost:8080

Agli baar sirf: `.\scripts\start-port-forwards.ps1` aur phir `.\scripts\start-dev.ps1` chalana hai.
