$ErrorActionPreference = "Stop"
$apiDirectory = Join-Path $PSScriptRoot "..\api"
$python = Join-Path $apiDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "API virtual environment not found: $python"
}

Push-Location $apiDirectory
try {
    & $python -m app.image_worker @args
}
finally {
    Pop-Location
}
