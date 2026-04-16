$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRef = "nelwkfazdgckyjeupphh"

function Get-EnvValue {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  $value = [Environment]::GetEnvironmentVariable($Name)
  if (-not [string]::IsNullOrWhiteSpace($value)) {
    return $value
  }

  $examplePath = Join-Path $root ".env.functions"
  if (Test-Path $examplePath) {
    $line = Get-Content $examplePath | Where-Object { $_ -match "^${Name}=" } | Select-Object -First 1
    if ($line) {
      return ($line -replace "^${Name}=", "").Trim('"')
    }
  }

  return ""
}

function Resolve-SupabaseCli {
  $localCli = Join-Path $root "node_modules\.bin\supabase.cmd"
  if (Test-Path $localCli) {
    return $localCli
  }

  $globalCli = Get-Command supabase -ErrorAction SilentlyContinue
  if ($globalCli) {
    return $globalCli.Source
  }

  throw "Supabase CLI was not found. Install it locally or globally first."
}

$supabaseAccessToken = Get-EnvValue -Name "SUPABASE_ACCESS_TOKEN"
$openAiKey = Get-EnvValue -Name "OPENAI_API_KEY"
$openAiModel = Get-EnvValue -Name "OPENAI_MODEL"
$lovableApiKey = Get-EnvValue -Name "LOVABLE_API_KEY"

if ([string]::IsNullOrWhiteSpace($supabaseAccessToken)) {
  throw "SUPABASE_ACCESS_TOKEN is missing. Add it to the environment or .env.functions."
}

if ([string]::IsNullOrWhiteSpace($openAiKey)) {
  throw "OPENAI_API_KEY is missing. Add it to the environment or .env.functions."
}

if ([string]::IsNullOrWhiteSpace($lovableApiKey)) {
  throw "LOVABLE_API_KEY is missing. Add it to the environment or .env.functions."
}

if ([string]::IsNullOrWhiteSpace($openAiModel)) {
  $openAiModel = "gpt-4o-mini"
}

$supabaseCli = Resolve-SupabaseCli
$env:SUPABASE_ACCESS_TOKEN = $supabaseAccessToken

& $supabaseCli secrets set `
  "OPENAI_API_KEY=$openAiKey" `
  "OPENAI_MODEL=$openAiModel" `
  "LOVABLE_API_KEY=$lovableApiKey" `
  --project-ref $projectRef

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

& $supabaseCli functions deploy crisis-chat --project-ref $projectRef --use-api
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

& $supabaseCli functions deploy fetch-news --project-ref $projectRef --use-api
exit $LASTEXITCODE
