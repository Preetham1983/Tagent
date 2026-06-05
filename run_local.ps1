# Start all Tagent services locally for testing
# Run from the project root: powershell -File run_local.ps1

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Starting Tagent Services ===" -ForegroundColor Cyan

# Start the orchestrator (which spawns MCP tools as a subprocess)
Write-Host "`n[1/2] Starting Orchestrator Service on :8001..." -ForegroundColor Green
$orchestratorJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location "$root\backend\services\orchestrator-service"
    uv run uvicorn main:app --host 0.0.0.0 --port 8001
} -ArgumentList $Root

# Give orchestrator a moment to start
Start-Sleep -Seconds 3

# Start the frontend
Write-Host "[2/2] Starting Frontend on :5173..." -ForegroundColor Green
$frontendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location "$root\frontend"
    npm run dev -- --host 0.0.0.0 --port 5173
} -ArgumentList $Root

Start-Sleep -Seconds 2

Write-Host "`n=== All Services Running ===" -ForegroundColor Cyan
Write-Host "  Orchestrator: http://localhost:8001" -ForegroundColor Yellow
Write-Host "  Frontend:     http://localhost:5173" -ForegroundColor Yellow
Write-Host "`nPress Ctrl+C to stop all services.`n" -ForegroundColor Gray

# Wait and show logs
try {
    while ($true) {
        Receive-Job $orchestratorJob 2>&1 | Write-Host
        Receive-Job $frontendJob 2>&1 | Write-Host
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "`nStopping services..." -ForegroundColor Red
    Stop-Job $orchestratorJob, $frontendJob
    Remove-Job $orchestratorJob, $frontendJob -Force
}
