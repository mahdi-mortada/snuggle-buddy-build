$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeDir = Join-Path $root ".tools\node-v22.14.0-win-x64"
$nodeExe = Join-Path $nodeDir "node.exe"
$npmCli = Join-Path $nodeDir "node_modules\npm\bin\npm-cli.js"
$nodeModules = Join-Path $root "node_modules"
$tmpDir = Join-Path $root ".tmp"
$apiStdout = Join-Path $tmpDir "local-api-stdout.log"
$apiStderr = Join-Path $tmpDir "local-api-stderr.log"
$backendStdout = Join-Path $tmpDir "backend-stdout.log"
$backendStderr = Join-Path $tmpDir "backend-stderr.log"
$backendRoot = Join-Path $root "backend"
$pythonExe = "C:\Users\MahdiMortada\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"
$backendHost = "127.0.0.1"
$preferredBackendPort = 8000
$fallbackBackendPort = 8010

function Test-CrisisShieldBackend {
  param(
    [string]$BackendHost,
    [int]$Port
  )

  try {
    $response = Invoke-RestMethod -Uri "http://${BackendHost}:${Port}/health" -TimeoutSec 2
    if ($response.success -eq $true -and $null -ne $response.data.seeded_users) {
      return $true
    }
  } catch {
    return $false
  }

  return $false
}

function Test-PortInUse {
  param([int]$Port)

  try {
    return [bool](Get-NetTCPConnection -LocalPort $Port -ErrorAction Stop | Select-Object -First 1)
  } catch {
    return $false
  }
}

if (-not (Test-Path $nodeExe)) {
  throw "Portable Node runtime was not found at $nodeExe."
}

if (-not (Test-Path $npmCli)) {
  throw "Portable npm CLI was not found at $npmCli."
}

$env:PATH = "$nodeDir;$env:PATH"
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

if (-not (Test-Path $pythonExe)) {
  throw "Python runtime was not found at $pythonExe."
}

if (-not (Test-Path $nodeModules)) {
  & $nodeExe $npmCli install
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

$apiHealthy = $false
try {
  $health = Invoke-WebRequest -Uri "http://127.0.0.1:8787/api/health" -UseBasicParsing -TimeoutSec 2
  if ($health.StatusCode -eq 200) {
    $apiHealthy = $true
  }
} catch {
  $apiHealthy = $false
}

if (-not $apiHealthy) {
  if (Test-Path $apiStdout) { Remove-Item -LiteralPath $apiStdout -Force }
  if (Test-Path $apiStderr) { Remove-Item -LiteralPath $apiStderr -Force }

  Start-Process -FilePath $nodeExe `
    -ArgumentList (Join-Path $root "local-api-server.mjs") `
    -WorkingDirectory $root `
    -RedirectStandardOutput $apiStdout `
    -RedirectStandardError $apiStderr | Out-Null
}

$backendPort = $preferredBackendPort
$backendHealthy = Test-CrisisShieldBackend -BackendHost $backendHost -Port $backendPort

if (-not $backendHealthy -and (Test-PortInUse -Port $preferredBackendPort)) {
  $backendPort = $fallbackBackendPort
  $backendHealthy = Test-CrisisShieldBackend -BackendHost $backendHost -Port $backendPort
}

if (-not $backendHealthy) {
  if (Test-Path $backendStdout) { Remove-Item -LiteralPath $backendStdout -Force }
  if (Test-Path $backendStderr) { Remove-Item -LiteralPath $backendStderr -Force }

  Start-Process -FilePath $pythonExe `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $backendHost, "--port", "$backendPort" `
    -WorkingDirectory $backendRoot `
    -RedirectStandardOutput $backendStdout `
    -RedirectStandardError $backendStderr | Out-Null
}

$env:VITE_BACKEND_URL = "http://${backendHost}:${backendPort}"
$env:VITE_BACKEND_WS_URL = "ws://${backendHost}:${backendPort}/ws/live-feed"

& $nodeExe $npmCli run dev:localhost
exit $LASTEXITCODE
