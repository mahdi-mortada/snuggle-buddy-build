$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path $PSScriptRoot).Path
$backendRoot = Join-Path $projectRoot "backend"
$dotVenvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$venvPython = Join-Path $projectRoot "venv\Scripts\python.exe"
$portablePython = "C:\Users\MahdiMortada\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"
$backendHost = "127.0.0.1"
$backendPort = 8010

if (Test-Path $dotVenvPython) {
  $python = $dotVenvPython
} elseif (Test-Path $venvPython) {
  $python = $venvPython
} elseif (Test-Path $portablePython) {
  $python = $portablePython
} else {
  $python = "python"
}

Write-Host "Starting CrisisShield backend from $backendRoot"
Write-Host "Using Python interpreter: $python"
Set-Location $backendRoot
& $python -m uvicorn app.main:app --host $backendHost --port $backendPort --reload
