$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeDir = Join-Path $projectRoot '.local'
if (-not (Test-Path "$runtimeDir\pgsql\bin\pg_ctl.exe")) { throw 'PostgreSQL local ainda não foi instalado.' }
Get-Content (Join-Path $projectRoot '.env') | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '5433'
& "$runtimeDir\pgsql\bin\pg_ctl.exe" -D "$runtimeDir\pgdata" status *> $null
if ($LASTEXITCODE -ne 0) {
    & "$runtimeDir\pgsql\bin\pg_ctl.exe" -D "$runtimeDir\pgdata" -l "$runtimeDir\postgres.log" -w start
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar PostgreSQL. Veja .local/postgres.log.' }
}
foreach ($port in @(8000,5173)) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($listener) { throw "Porta $port já está ocupada. Se EngFinance estiver aberto, use-o ou execute stop-local.ps1 antes." }
}
$backend = Start-Process -FilePath "$projectRoot\.venv\Scripts\python.exe" -ArgumentList 'manage.py','runserver','127.0.0.1:8000','--noreload' -WorkingDirectory "$projectRoot\backend" -WindowStyle Hidden -RedirectStandardOutput "$runtimeDir\backend.log" -RedirectStandardError "$runtimeDir\backend-error.log" -PassThru
$frontend = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList 'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort' -WorkingDirectory "$projectRoot\frontend" -WindowStyle Hidden -RedirectStandardOutput "$runtimeDir\frontend.log" -RedirectStandardError "$runtimeDir\frontend-error.log" -PassThru
@{backend=$backend.Id;frontend=$frontend.Id} | ConvertTo-Json | Set-Content "$runtimeDir\server-pids.json"
Write-Output 'EngFinance iniciando em http://127.0.0.1:5173. Logs na pasta .local.'
