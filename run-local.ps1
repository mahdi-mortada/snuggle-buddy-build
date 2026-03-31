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

$backendHealthy = $false
try {
  $backendHealth = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
  if ($backendHealth.StatusCode -eq 200) {
    $backendHealthy = $true
  }
} catch {
  $backendHealthy = $false
}

if (-not $backendHealthy) {
  if (Test-Path $backendStdout) { Remove-Item -LiteralPath $backendStdout -Force }
  if (Test-Path $backendStderr) { Remove-Item -LiteralPath $backendStderr -Force }

  Start-Process -FilePath $pythonExe `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $backendRoot `
    -RedirectStandardOutput $backendStdout `
    -RedirectStandardError $backendStderr | Out-Null
}

& $nodeExe $npmCli run dev:localhost
exit $LASTEXITCODE
