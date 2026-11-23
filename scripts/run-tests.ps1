<#
  Runs all tests and saves the REAL output to docs\test-results\ (evidence for the report).
    -Live : also run the integration tests against your cluster + Prometheus (needs port-forward)
  Usage:  .\scripts\run-tests.ps1 [-Live]
#>
param([switch]$Live)
$root = Split-Path $PSScriptRoot -Parent
$results = Join-Path $root "docs\test-results"
New-Item -ItemType Directory -Force -Path $results | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"

Push-Location (Join-Path $root "backend")
if (Test-Path .\.venv\Scripts\Activate.ps1) { . .\.venv\Scripts\Activate.ps1 }
if ($Live) { $env:LIVE_TESTS = "1" } else { Remove-Item Env:LIVE_TESTS -ErrorAction SilentlyContinue }
"Run at $stamp (LIVE_TESTS=$($env:LIVE_TESTS))" | Out-File "$results\backend-pytest.txt" -Encoding utf8
python -m pytest -v -rs 2>&1 | Tee-Object -FilePath "$results\backend-pytest.txt" -Append
$backendCode = $LASTEXITCODE
Pop-Location

Push-Location (Join-Path $root "frontend")
"Run at $stamp" | Out-File "$results\frontend-vitest.txt" -Encoding utf8
npx vitest run --reporter=verbose 2>&1 | Tee-Object -FilePath "$results\frontend-vitest.txt" -Append
$frontendCode = $LASTEXITCODE
Pop-Location

Write-Host ""
Write-Host "Backend tests : $(if ($backendCode -eq 0) {'PASSED'} else {'FAILED (exit ' + $backendCode + ')'})"
Write-Host "Frontend tests: $(if ($frontendCode -eq 0) {'PASSED'} else {'FAILED (exit ' + $frontendCode + ')'})"
Write-Host "Saved to $results"
