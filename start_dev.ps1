param(
    [switch]$NoBrowser,
    [switch]$WithPrototype
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$PrototypeRoot = Join-Path $ProjectRoot "docs\prototype"
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
if ($WithPrototype) {
    Stop-PortProcess 4173
}

# 让子进程继承模块搜索路径，直接启动可执行文件，避免嵌套 PowerShell 的转义问题。
$env:PYTHONPATH = "$ProjectRoot\packages\arena\src;$ProjectRoot\packages\arena_api\src"

Start-Process -FilePath $Python `
    -ArgumentList @("-m", "arena.server.cli") `
    -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null

Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
    -WorkingDirectory $FrontendRoot -WindowStyle Hidden | Out-Null

if ($WithPrototype) {
    if (-not (Test-Path (Join-Path $PrototypeRoot "index.html"))) {
        throw "找不到原型入口：$PrototypeRoot\index.html"
    }
    Start-Process -FilePath $Python `
        -ArgumentList @("-m", "http.server", "4173", "--bind", "127.0.0.1", "--directory", $PrototypeRoot) `
        -WorkingDirectory $PrototypeRoot `
        -WindowStyle Hidden | Out-Null
}

Start-Sleep -Seconds 2
Write-Host "后端: http://127.0.0.1:8765"
Write-Host "前端: http://127.0.0.1:3000"
if ($WithPrototype) {
    Write-Host "原型: http://127.0.0.1:4173/index.html"
}

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:3000"
    if ($WithPrototype) {
        Start-Process "http://127.0.0.1:4173/index.html"
    }
}
