<#
  Starts the two port-forwards the platform needs, each in its own minimized PowerShell window.
    Prometheus : http://127.0.0.1:9091   (svc/prometheus-operator-kube-p-prometheus in namespace monitoring)
    Jaeger     : http://127.0.0.1:16686  (svc/tracing in namespace istio-system, optional)

  Usage:
    .\scripts\start-port-forwards.ps1               # for running the backend directly on Windows
    .\scripts\start-port-forwards.ps1 -ListenAll    # for Docker Compose, if the container cannot reach 127.0.0.1
  Close the two windows to stop the port-forwards.
#>
param(
    [string]$Context = "docker-desktop",
    [string]$PrometheusService = "prometheus-operator-kube-p-prometheus",
    [int]$PrometheusPort = 9091,
    [switch]$ListenAll
)

$address = if ($ListenAll) { "0.0.0.0" } else { "127.0.0.1" }

function Start-Forward($Title, $Namespace, $Service, $LocalPort, $RemotePort) {
    kubectl --context $Context get svc $Service -n $Namespace *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "SKIP  $Title : service $Namespace/$Service not found (kubectl get svc -n $Namespace)" -ForegroundColor Yellow
        return
    }
    $cmd = "`$Host.UI.RawUI.WindowTitle='port-forward $Title'; " +
           "while (`$true) { kubectl --context $Context port-forward --address $address -n $Namespace svc/$Service ${LocalPort}:${RemotePort}; " +
           "Write-Host 'port-forward stopped, restarting in 3 s...'; Start-Sleep 3 }"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Minimized
    Write-Host "START $Title : http://127.0.0.1:$LocalPort  ($Namespace/$Service, listening on $address)" -ForegroundColor Green
}

Start-Forward "Prometheus" "monitoring" $PrometheusService $PrometheusPort 9090
Start-Forward "Jaeger" "istio-system" "tracing" 16686 80

Start-Sleep 4
try {
    $v = (Invoke-RestMethod "http://127.0.0.1:$PrometheusPort/api/v1/status/buildinfo" -TimeoutSec 5).data.version
    Write-Host "Prometheus is reachable (version $v)" -ForegroundColor Green
} catch {
    Write-Host "Prometheus not reachable yet - wait a few seconds, then open http://127.0.0.1:$PrometheusPort" -ForegroundColor Yellow
}
