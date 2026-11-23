<#
  Creates .kube-docker\config: a minimal kubeconfig that ONLY the backend container mounts (read-only).

  Why: your normal kubeconfig points to https://127.0.0.1:<port> (or kubernetes.docker.internal).
  Inside a container 127.0.0.1 is the container itself, so the server address is changed to
  host.docker.internal, and tls-server-name keeps the TLS certificate check working.

  The file contains your cluster credentials: it is in .gitignore - never commit or share it.
  Usage:  .\scripts\make-docker-kubeconfig.ps1 [-Context docker-desktop]
#>
param([string]$Context = "docker-desktop")

$root = Split-Path $PSScriptRoot -Parent
$outDir = Join-Path $root ".kube-docker"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$out = Join-Path $outDir "config"

$yaml = kubectl config view --minify --flatten --context $Context
if ($LASTEXITCODE -ne 0) { Write-Host "kubectl config view failed - is the context '$Context' correct?" -ForegroundColor Red; exit 1 }
$yaml = $yaml -join "`n"

if ($yaml -match 'server:\s*https://([^:/\s]+):(\d+)') {
    $origHost = $Matches[1]; $port = $Matches[2]
    $tlsName = if ($origHost -eq "127.0.0.1") { "localhost" } else { $origHost }
    $yaml = $yaml -replace "server:\s*https://[^:/\s]+:$port", "server: https://host.docker.internal:$port`n    tls-server-name: $tlsName"
    Write-Host "API server $origHost`:$port  ->  host.docker.internal`:$port  (tls-server-name: $tlsName)" -ForegroundColor Green
} else {
    Write-Host "Could not find the server address in the kubeconfig; file written unchanged." -ForegroundColor Yellow
}

[System.IO.File]::WriteAllText($out, $yaml)
Write-Host "Written: $out" -ForegroundColor Green
Write-Host "This file holds credentials. It is git-ignored; do not share it." -ForegroundColor Yellow
