<#
 ====================================================================
 RiskMouse - Start / Restart Script (PowerShell)
 Auto kill old process -> check env -> start service
 ====================================================================
 Usage:
   .\start.ps1                # start/restart (default port 8787)
   .\start.ps1 -Port 5000     # specify port
   .\start.ps1 -Action stop   # stop only
 ====================================================================
#>

param(
    [ValidateSet("start", "stop", "restart")]
    [string]$Action = "start",
    [int]$Port = 8787
)

$ErrorActionPreference = "Continue"

function Info  { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Ok    { Write-Host "[OK]   $args" -ForegroundColor Green }
function Warn  { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Err   { Write-Host "[ERR]  $args" -ForegroundColor Red }

function Stop-Server {
    $found = $null
    $lines = netstat -ano 2>$null
    foreach ($line in $lines) {
        if ($line -match ":$Port " -and $line -match "LISTEN") {
            $parts = $line -split '\s+'
            $found = $parts[-1]
            break
        }
    }
    if ($found) {
        Warn "Found old process on port $Port (PID: $found), stopping..."
        Stop-Process -Id $found -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        Ok "Old process stopped"
    } else {
        Info "No process on port $Port, nothing to stop"
    }
}

function Check-Env {
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Err "Created .env from .env.example - please edit and fill in your API Key, then re-run"
            exit 1
        } else {
            Err ".env.example not found either - please create .env first"
            exit 1
        }
    }
    Ok ".env ready"
}

function Get-UvicornPath {
    $paths = @(
        ".venv\Scripts\uvicorn.exe",
        ".venv\Scripts\uvicorn",
        ".venv\bin\uvicorn"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    Err "Virtual environment (.venv) not found - please create it first:"
    Err "  python -m venv .venv"
    Err "  .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

function Start-Server {
    param([string]$UvicornPath)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  RiskMouse" -ForegroundColor Cyan
    Write-Host "  Port: $Port" -ForegroundColor Cyan
    Write-Host "  URL:  http://localhost:$Port" -ForegroundColor Cyan
    Write-Host "  Docs: http://localhost:$Port/docs" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    & $UvicornPath backend.app.main:app --host 0.0.0.0 --port $Port
}

Write-Host ""
Write-Host "+---------------------------------------+" -ForegroundColor Cyan
Write-Host "|  RiskMouse - Start Script              |" -ForegroundColor Cyan
Write-Host "+---------------------------------------+" -ForegroundColor Cyan
Write-Host ""

switch ($Action) {
    "stop" {
        Stop-Server
        Ok "Service stopped"
        exit 0
    }
    default {
        Stop-Server
        Check-Env
        $uvicorn = Get-UvicornPath
        Start-Server -UvicornPath $uvicorn
    }
}
