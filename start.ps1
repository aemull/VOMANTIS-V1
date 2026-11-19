$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Virtual environment belum tersedia. Ikuti langkah instalasi di README.md.'
}
Push-Location $projectDirectory
try {
    & $pythonExecutable manage.py migrate
    if ($LASTEXITCODE -ne 0) { throw 'Migrasi gagal.' }
    & $pythonExecutable manage.py create_roles
    if ($LASTEXITCODE -ne 0) { throw 'Pembuatan grup gagal.' }
    & $pythonExecutable manage.py generate_schedules
    if ($LASTEXITCODE -ne 0) { throw 'Penjadwalan awal gagal.' }
    $schedulerProcess = Start-Process -FilePath $pythonExecutable -ArgumentList @('manage.py', 'run_scheduler') -WorkingDirectory $projectDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectDirectory 'scheduler.log') -RedirectStandardError (Join-Path $projectDirectory 'scheduler-error.log')
    Write-Host 'VOMANTIS: http://127.0.0.1:8000/ (penjadwal otomatis aktif selama script berjalan)'
    & $pythonExecutable manage.py runserver 127.0.0.1:8000
} finally {
    if ($schedulerProcess -and -not $schedulerProcess.HasExited) { $schedulerProcess.Kill() }
    Pop-Location
}
