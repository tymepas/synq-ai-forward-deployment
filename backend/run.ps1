$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $backendRoot
$venvPython = Join-Path $backendRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    python -m venv (Join-Path $backendRoot '.venv')
}

& $venvPython -m pip install --disable-pip-version-check -e $backendRoot
& $venvPython -m app.run
