param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$Python = "D:\00_Inbox\Anaconda\python.exe"

if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

function Stop-PortProcess([int]$Port) {
    $connections = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "停止端口 $Port 上的进程 $($process.Id) ($($process.ProcessName))"
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

Stop-PortProcess 8765
Stop-PortProcess 3000

$backendCommand = @"
`$env:PYTHONPATH = `"$ProjectRoot\packages\arena\src;$ProjectRoot\packages\arena_api\src`"
Set-Location `"$ProjectRoot`"
& `"$Python`" -m arena.server.cli
"@

$frontendCommand = @"
Set-Location `"$FrontendRoot`"
npm run dev -- --host 127.0.0.1
"@

Start-Process powershell.exe -ArgumentList @(
    "-NoLogo", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand
) -WorkingDirectory $ProjectRoot | Out-Null

Start-Process powershell.exe -ArgumentList @(
    "-NoLogo", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand
) -WorkingDirectory $FrontendRoot | Out-Null

Start-Sleep -Seconds 2
Write-Host "后端: http://127.0.0.1:8765"
Write-Host "前端: http://127.0.0.1:3000"

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:3000"
}
