param(
    [switch]$NoBrowser,
    [int]$Port = 4173
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PrototypeRoot = Join-Path $ProjectRoot "docs\prototype"
$Python = "D:\00_Inbox\Anaconda\python.exe"

if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

if (-not (Test-Path (Join-Path $PrototypeRoot "index.html"))) {
    throw "找不到原型入口：$PrototypeRoot\index.html"
}

$connections = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
foreach ($connection in $connections) {
    $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "停止端口 $Port 上的进程 $($process.Id) ($($process.ProcessName))"
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

Start-Process -FilePath $Python `
    -ArgumentList @("-m", "http.server", $Port, "--bind", "127.0.0.1", "--directory", $PrototypeRoot) `
    -WorkingDirectory $PrototypeRoot `
    -WindowStyle Hidden | Out-Null

Start-Sleep -Milliseconds 500
Write-Host "原型: http://127.0.0.1:$Port/index.html"

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:$Port/index.html"
}
