$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeDir = Join-Path $projectRoot '.local'
$pidFile = Join-Path $runtimeDir 'server-pids.json'
if (Test-Path $pidFile) {
    $servers = Get-Content $pidFile -Raw | ConvertFrom-Json
    foreach ($serverId in @($servers.backend, $servers.frontend)) {
        $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId"
        if ($serverProcess -and ($serverProcess.CommandLine -match 'manage\.py.*runserver|node_modules[/\\]vite[/\\]bin[/\\]vite\.js')) {
            Stop-Process -Id $serverId
        }
    }
}
& "$runtimeDir\pgsql\bin\pg_ctl.exe" -D "$runtimeDir\pgdata" -m fast -w stop
Write-Output 'Serviços locais encerrados.'
