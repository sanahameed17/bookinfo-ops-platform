<#
  Phase 1 - READ-ONLY environment inspection for the Bookinfo Observability project.

  What it does:
    * Records tool versions (Docker, kubectl, kind, Python, Node, Git, Helm)
    * Inspects the kind cluster, the bookinfo and monitoring namespaces, and Istio
    * Tests Prometheus (if reachable) with the PromQL queries the backend will need
    * Checks what your earlier labs already deployed (Istio, Grafana, Jaeger, Chaos Mesh)
    * Lists the files in each Lab folder and makes a ZIP of its source code
      WITHOUT .env files, virtualenvs, node_modules, .git or kubeconfig files

  What it does NOT do:
    * It never creates, deletes, restarts, scales or edits anything in Kubernetes
      (only "get", "describe"-style reads, "top" and "config view").
    * It never prints secret values. kubeconfig certificates are redacted by kubectl,
      and only the variable NAMES from .env files are listed, never their values.

  Usage (PowerShell, from the folder where you saved this file):
    powershell -ExecutionPolicy Bypass -File .\inspect-env.ps1 -LabPaths "C:\path\to\lab1","C:\path\to\lab2","C:\path\to\lab3"

  Output:
    .\phase1-report.txt   -> upload this
    .\source-<folder>.zip -> one per lab folder, upload these
#>
param(
    [string[]]$LabPaths = @(),
    [string]$ProjectPath = "",
    [string]$Namespace = "bookinfo",
    [string]$MonitoringNamespace = "monitoring",
    [string]$ExpectedContext = "docker-desktop",
    [string]$PrometheusUrl = "http://127.0.0.1:9091"
)

$ErrorActionPreference = "Continue"
# Your Windows system proxy (Clash, 127.0.0.1:10090) can intercept localhost requests.
# Use NO proxy for the web requests this script makes (Prometheus / Jaeger on 127.0.0.1).
[System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy
$Out = Join-Path (Get-Location) "phase1-report.txt"
"Phase 1 inspection report - generated $(Get-Date -Format o)" | Out-File -FilePath $Out -Encoding utf8

function Write-Section {
    param([string]$Title, [scriptblock]$Block)
    Write-Host "-> $Title" -ForegroundColor Cyan
    "`r`n===== $Title =====" | Out-File -FilePath $Out -Append -Encoding utf8
    try {
        & $Block 2>&1 | Out-String -Width 400 | Out-File -FilePath $Out -Append -Encoding utf8
    } catch {
        "ERROR: $($_.Exception.Message)" | Out-File -FilePath $Out -Append -Encoding utf8
    }
}

function Test-Cmd([string]$Name) { [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

# ---------------------------------------------------------------- 1. Tools
Write-Section "OS" { [System.Environment]::OSVersion.VersionString; $PSVersionTable.PSVersion.ToString() }
foreach ($t in @(
    @{n="docker";  a=@("version","--format","Client {{.Client.Version}} / Server {{.Server.Version}}")},
    @{n="kubectl"; a=@("version","--client")},
    @{n="kind";    a=@("version")},
    @{n="helm";    a=@("version","--short")},
    @{n="istioctl";a=@("version","--remote=false")},
    @{n="python";  a=@("--version")},
    @{n="node";    a=@("--version")},
    @{n="npm";     a=@("--version")},
    @{n="git";     a=@("--version")}
)) {
    $name = $t.n; $cmdArgs = $t.a
    Write-Section "Tool: $name" {
        if (Test-Cmd $name) { & $name @cmdArgs } else { "NOT INSTALLED / not on PATH" }
    }
}
Write-Section "Docker engine" { docker info --format "OS={{.OperatingSystem}} CPUs={{.NCPU}} Mem={{.MemTotal}} Containers={{.Containers}}" }
Write-Section "Running containers" { docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" }

# ---------------------------------------------------------------- 2. Cluster / context
Write-Section "kind clusters" { kind get clusters }
Write-Section "kubectl contexts" { kubectl config get-contexts }
Write-Section "Current context (expected: $ExpectedContext)" {
    $ctx = kubectl config current-context
    $ctx
    if ($ctx -ne $ExpectedContext) { "WARNING: current context is not $ExpectedContext" }
}
Write-Section "Active kubeconfig (certificates redacted by kubectl)" { kubectl config view --minify }
Write-Section "API server ready" { kubectl get --raw /readyz }
Write-Section "Nodes" { kubectl get nodes -o wide }
Write-Section "Namespaces" { kubectl get namespaces --show-labels }

# ---------------------------------------------------------------- 3. Bookinfo resources
Write-Section "Bookinfo: Services" {
    kubectl get svc -n $Namespace -o custom-columns="NAME:.metadata.name,TYPE:.spec.type,CLUSTER-IP:.spec.clusterIP,PORTS:.spec.ports[*].port,PORTNAMES:.spec.ports[*].name,SELECTOR:.spec.selector,CREATED:.metadata.creationTimestamp"
}
Write-Section "Bookinfo: Deployments" { kubectl get deploy -n $Namespace -o wide --show-labels }
Write-Section "Bookinfo: Deployment pod-template labels" {
    kubectl get deploy -n $Namespace -o custom-columns="NAME:.metadata.name,TEMPLATE-LABELS:.spec.template.metadata.labels,REPLICAS:.spec.replicas"
}
Write-Section "Bookinfo: Container resources (requests/limits)" {
    kubectl get deploy -n $Namespace -o custom-columns="NAME:.metadata.name,CONTAINERS:.spec.template.spec.containers[*].name,RESOURCES:.spec.template.spec.containers[*].resources"
}
Write-Section "Bookinfo: Probes" {
    kubectl get deploy -n $Namespace -o custom-columns="NAME:.metadata.name,READINESS:.spec.template.spec.containers[*].readinessProbe,LIVENESS:.spec.template.spec.containers[*].livenessProbe"
}
Write-Section "Bookinfo: ReplicaSets" { kubectl get rs -n $Namespace -o wide }
Write-Section "Bookinfo: Pods" { kubectl get pods -n $Namespace -o wide --show-labels }
Write-Section "Bookinfo: Pod details" {
    kubectl get pods -n $Namespace -o custom-columns="POD:.metadata.name,PHASE:.status.phase,OWNER:.metadata.ownerReferences[0].name,CONTAINERS:.spec.containers[*].name,IMAGES:.spec.containers[*].image,READY:.status.containerStatuses[*].ready,RESTARTS:.status.containerStatuses[*].restartCount"
}
Write-Section "Bookinfo: Container waiting reasons (CrashLoopBackOff etc.)" {
    kubectl get pods -n $Namespace -o custom-columns="POD:.metadata.name,WAITING:.status.containerStatuses[*].state.waiting.reason,LAST-TERMINATED:.status.containerStatuses[*].lastState.terminated.reason"
}
Write-Section "Bookinfo: Endpoints" { kubectl get endpoints -n $Namespace }
Write-Section "Bookinfo: Recent events" { kubectl get events -n $Namespace --sort-by=.lastTimestamp }
Write-Section "metrics-server (kubectl top)" { kubectl top pods -n $Namespace --containers }

# ---------------------------------------------------------------- 4. Istio
Write-Section "Istio namespace" { kubectl get pods -n istio-system -o wide }
Write-Section "Istio CRDs" { kubectl get crd -o name | Select-String "istio" }
Write-Section "Istio sidecar injection label on $Namespace" { kubectl get ns $Namespace -o custom-columns="NAME:.metadata.name,LABELS:.metadata.labels" }
Write-Section "Istio routing resources in $Namespace" {
    kubectl get virtualservices,destinationrules,gateways,serviceentries -n $Namespace -o wide
}

# ---------------------------------------------------------------- 5. Monitoring stack
Write-Section "Monitoring: Pods" { kubectl get pods -n $MonitoringNamespace -o wide }
Write-Section "Monitoring: Services (look for the Prometheus one)" { kubectl get svc -n $MonitoringNamespace }
Write-Section "Helm releases" { if (Test-Cmd "helm") { helm list -A } else { "helm not installed" } }
Write-Section "Is anything listening on local port 9091 (Prometheus port-forward)?" {
    $l = Get-NetTCPConnection -LocalPort 9091 -State Listen -ErrorAction SilentlyContinue
    if ($l) { $l | Format-Table LocalAddress, LocalPort, OwningProcess -AutoSize
              $l | ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, Path } }
    else { "Nothing is listening on port 9091. Prometheus port-forward is NOT running." }
}

# ---------------------------------------------------------------- 5b. Existing lab components (reuse check)
Write-Section "All Pods in all namespaces (what is already deployed)" { kubectl get pods -A -o wide }
Write-Section "All Services in all namespaces" { kubectl get svc -A }
Write-Section "Grafana / Jaeger / Kiali / Prometheus services anywhere" {
    kubectl get svc -A | Select-String -Pattern "grafana|jaeger|tracing|zipkin|kiali|prometheus|alertmanager|kube-state-metrics|node-exporter"
}
Write-Section "Chaos Mesh components" { kubectl get pods -n chaos-mesh -o wide }
Write-Section "Chaos Mesh CRDs" { kubectl get crd -o name | Select-String "chaos-mesh" }
Write-Section "Chaos experiments still present (these can make Pods look unhealthy)" {
    kubectl get podchaos,networkchaos,stresschaos,iochaos,httpchaos,dnschaos,timechaos,schedules,workflows -A
}
Write-Section "ServiceMonitors / PodMonitors (Prometheus Operator)" { kubectl get servicemonitors,podmonitors -A }
Write-Section "Prometheus scrape config source (ConfigMaps mentioning prometheus)" {
    kubectl get configmap -n $MonitoringNamespace | Select-String "prometheus"
}

Write-Section "Windows system proxy (Clash) - must be bypassed for localhost" {
    Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" |
        Select-Object ProxyEnable, ProxyServer, ProxyOverride | Format-List
}
Write-Section "Jaeger service and dependency API (needs: kubectl port-forward -n istio-system svc/tracing 16686:80)" {
    kubectl get svc -n istio-system
    try {
        $end = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
        $d = Invoke-RestMethod -Uri "http://127.0.0.1:16686/jaeger/api/dependencies?endTs=$end&lookback=86400000" -TimeoutSec 5 -ErrorAction Stop
        "Jaeger dependencies (/jaeger prefix):"; $d.data | Format-Table parent, child, callCount -AutoSize
    } catch {
        try {
            $d = Invoke-RestMethod -Uri "http://127.0.0.1:16686/api/dependencies?endTs=$end&lookback=86400000" -TimeoutSec 5 -ErrorAction Stop
            "Jaeger dependencies:"; $d.data | Format-Table parent, child, callCount -AutoSize
        } catch { "Jaeger API not reachable on 127.0.0.1:16686 (port-forward not running?) - $($_.Exception.Message)" }
    }
}

# ---------------------------------------------------------------- 6. Prometheus queries
function Invoke-Prom([string]$Query) {
    $u = "$PrometheusUrl/api/v1/query?query=" + [uri]::EscapeDataString($Query)
    $r = Invoke-RestMethod -Uri $u -TimeoutSec 10
    "status=$($r.status)  resultType=$($r.data.resultType)  series=$(@($r.data.result).Count)"
    @($r.data.result) | Select-Object -First 15 | ForEach-Object {
        ($_.metric | ConvertTo-Json -Compress) + "  =>  " + $_.value[1]
    }
}
$promUp = $false
Write-Section "Prometheus reachability ($PrometheusUrl)" {
    $b = Invoke-RestMethod -Uri "$PrometheusUrl/api/v1/status/buildinfo" -TimeoutSec 5
    "Prometheus version: $($b.data.version)"
    $script:promUp = $true
}
if ($promUp) {
    $ns = $Namespace
    $queries = [ordered]@{
        "Scrape targets per job"                  = 'count by (job) (up)'
        "Targets that are DOWN"                   = 'up == 0'
        "cAdvisor CPU series present (bookinfo)"  = "count by (pod, container) (container_cpu_usage_seconds_total{namespace=`"$ns`"})"
        "CPU cores per pod (5m rate)"             = "sum by (pod) (rate(container_cpu_usage_seconds_total{namespace=`"$ns`",container!=`"`",container!=`"POD`"}[5m]))"
        "CPU cores per container (5m rate)"       = "sum by (pod, container) (rate(container_cpu_usage_seconds_total{namespace=`"$ns`",container!=`"`",container!=`"POD`"}[5m]))"
        "Memory working set MiB per pod"          = "sum by (pod) (container_memory_working_set_bytes{namespace=`"$ns`",container!=`"`",container!=`"POD`"}) / 1048576"
        "kube-state-metrics: restarts"            = "kube_pod_container_status_restarts_total{namespace=`"$ns`"}"
        "kube-state-metrics: pod phase"           = "kube_pod_status_phase{namespace=`"$ns`"} == 1"
        "kube-state-metrics: deployment replicas" = "kube_deployment_status_replicas_available{namespace=`"$ns`"}"
        "kube-state-metrics: resource requests"   = "kube_pod_container_resource_requests{namespace=`"$ns`"}"
        "Istio traffic edges (for dependencies)"  = "sum by (source_workload, destination_workload) (istio_requests_total{destination_workload_namespace=`"$ns`"})"
    }
    foreach ($k in $queries.Keys) {
        $q = $queries[$k]
        Write-Section "PromQL: $k`r`n  $q" { Invoke-Prom $q }
    }
} else {
    "`r`nPrometheus not reachable at $PrometheusUrl - PromQL checks skipped." | Out-File -FilePath $Out -Append -Encoding utf8
}

# ---------------------------------------------------------------- 7. Lab 1/2/3 source code
$exclude = '\\(\.venv|venv|env|node_modules|__pycache__|\.git|dist|build)\\'
$zips = @()
if ($LabPaths.Count -eq 0) {
    "`r`nNo -LabPaths given - lab source inspection skipped." | Out-File -FilePath $Out -Append -Encoding utf8
}
foreach ($LabPath in $LabPaths) {
    if (-not (Test-Path $LabPath)) {
        "`r`nLab path not found: $LabPath" | Out-File -FilePath $Out -Append -Encoding utf8
        continue
    }
    $root = (Resolve-Path $LabPath).Path
    $leaf = Split-Path $root -Leaf
    Write-Section "Lab folder '$leaf': file list ($root)" {
        Get-ChildItem -Path $root -Recurse -File -Force |
            Where-Object { $_.FullName -notmatch $exclude } |
            ForEach-Object { "{0,10}  {1}" -f $_.Length, $_.FullName.Substring($root.Length) }
    }
    Write-Section "Lab folder '$leaf': .env variable NAMES only (values hidden)" {
        Get-ChildItem -Path $root -Recurse -File -Force -Filter ".env*" |
            Where-Object { $_.FullName -notmatch $exclude } |
            ForEach-Object {
                "--- $($_.FullName.Substring($root.Length))"
                Get-Content $_.FullName | Where-Object { $_ -match '^\s*[A-Za-z_][A-Za-z0-9_]*\s*=' } |
                    ForEach-Object { ($_ -split '=', 2)[0].Trim() + "=<hidden>" }
            }
    }
    Write-Section "Lab folder '$leaf': packaging source (secrets excluded)" {
        $tmp = Join-Path $env:TEMP "lab-src-copy-$leaf"
        if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
        robocopy $root $tmp /E /NFL /NDL /NJH /NJS /XD .venv venv env node_modules __pycache__ .git dist build /XF .env .env.* *.pem *.key *.crt kubeconfig* config | Out-Null
        $zip = Join-Path (Get-Location) "source-$leaf.zip"
        if (Test-Path $zip) { Remove-Item $zip -Force }
        Compress-Archive -Path (Join-Path $tmp "*") -DestinationPath $zip
        Remove-Item $tmp -Recurse -Force
        $script:zips += $zip
        "Created $zip"
    }
}

# ---------------------------------------------------------------- 8. New project folder (optional)
if ($ProjectPath -and (Test-Path $ProjectPath)) {
    Write-Section "Project folder contents ($ProjectPath)" {
        Get-ChildItem -Path $ProjectPath -Recurse -Force -Depth 2 |
            Where-Object { $_.FullName -notmatch '\\(node_modules|\.venv|\.git)\\' } |
            Select-Object Mode, Length, FullName | Format-Table -AutoSize
    }
}

Write-Host "`nDone. Report written to: $Out" -ForegroundColor Green
foreach ($z in $zips) { Write-Host "Source ZIP: $z" -ForegroundColor Green }
Write-Host "Before uploading, open phase1-report.txt and check that it contains nothing you consider private." -ForegroundColor Yellow
