$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path $PSScriptRoot).Path
$backendRoot = Join-Path $projectRoot "backend"
$portablePython = "C:\Users\MahdiMortada\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"
$backendHost = "127.0.0.1"
$backendPort = 8010

if (Test-Path $portablePython) {
  $python = $portablePython
} else {
  $python = "python"
}

Write-Host "Starting CrisisShield backend from $backendRoot"
Set-Location $backendRoot
& $python -m uvicorn app.main:app --host $backendHost --port $backendPort --reload
