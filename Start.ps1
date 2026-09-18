param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (!(Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython) { & $bundledPython -m venv .venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { python -m venv .venv }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 -m venv .venv }
    else { throw 'Install Python 3.12, then run Start.ps1 again.' }
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
    & ./.venv/Scripts/python.exe -m pip install --upgrade 'pip>=26.2.1'
    if ($LASTEXITCODE -ne 0) { throw 'pip update failed.' }
    & ./.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (!(Test-Path -LiteralPath 'dist/index.html')) {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
Write-Host "Open http://127.0.0.1:$Port in your browser. Stop with Ctrl+C."
& ./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
