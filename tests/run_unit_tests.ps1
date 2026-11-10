$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    python -m unittest discover -s tests -p "test_*.py" -v
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
