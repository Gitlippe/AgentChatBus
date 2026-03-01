# stop.ps1
# Immediately stop AgentChatBus without restarting.
# Usage:  .\scripts\stop.ps1
# Usage (custom port):  .\scripts\stop.ps1 -Port 8080

param(
    [int]$Port = 39765
)

Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "🛑 Stopping AgentChatBus (port $Port)..." -ForegroundColor Yellow

# Kill entire process tree of any Python running src.main
# uvicorn --reload spawns: reloader (parent) + server worker (child).
# taskkill /T kills the whole tree; Stop-Process only kills the single PID.
$found = $false
$pids = Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*src.main*" } |
    Select-Object -ExpandProperty Id

foreach ($p in $pids) {
    taskkill /PID $p /F /T 2>$null | Out-Null
    $found = $true
}

# Also free the port in case a stray process is still holding it
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess |
    ForEach-Object {
        taskkill /PID $_ /F /T 2>$null | Out-Null
        $found = $true
    }

if ($found) {
    Write-Host "✅ AgentChatBus stopped." -ForegroundColor Green
} else {
    Write-Host "ℹ️  No AgentChatBus process found on port $Port." -ForegroundColor Cyan
}
