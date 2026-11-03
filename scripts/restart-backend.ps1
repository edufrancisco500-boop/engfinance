$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$runtimeDir=Join-Path $projectRoot '.local'
Get-Content "$projectRoot\.env" | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1],$matches[2],'Process') }
}
$env:POSTGRES_HOST='127.0.0.1'
$env:POSTGRES_PORT='5433'
$servers=Get-Content "$runtimeDir\server-pids.json" -Raw | ConvertFrom-Json
$backendId=$servers.backend
$current=Get-CimInstance Win32_Process -Filter "ProcessId=$backendId"
if ($current -and $current.ExecutablePath -eq "$projectRoot\.venv\Scripts\python.exe" -and $current.CommandLine -match 'manage\.py.*runserver') {
    $children=Get-CimInstance Win32_Process -Filter "ParentProcessId=$backendId"
    foreach($child in $children) {
        if($child.CommandLine -match 'manage\.py.*runserver') { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
    }
    Stop-Process -Id $backendId -ErrorAction SilentlyContinue
}
$backend=Start-Process -FilePath "$projectRoot\.venv\Scripts\python.exe" -ArgumentList 'manage.py','runserver','127.0.0.1:8000','--noreload' -WorkingDirectory "$projectRoot\backend" -WindowStyle Hidden -RedirectStandardOutput "$runtimeDir\backend.log" -RedirectStandardError "$runtimeDir\backend-error.log" -PassThru
$servers.backend=$backend.Id
$servers | ConvertTo-Json | Set-Content "$runtimeDir\server-pids.json"
Write-Output 'Backend reiniciado. Frontend e banco foram preservados.'
