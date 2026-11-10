param(
    [switch]$StrictCamera
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$candidates = @()
if ($env:BLENDER_EXE) { $candidates += $env:BLENDER_EXE }
$cmd = Get-Command blender -ErrorAction SilentlyContinue
if ($cmd) { $candidates += $cmd.Source }
$candidates += @(
    "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
)

$blender = $null
foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $blender = $candidate
        break
    }
}

if (-not $blender) {
    Write-Error "Blender not found. Set BLENDER_EXE to blender.exe."
    exit 2
}

$env:BTS_REPO = $repo
if ($StrictCamera) { $env:BTS_STRICT_CAMERA = "1" } else { Remove-Item Env:BTS_STRICT_CAMERA -ErrorAction SilentlyContinue }

& $blender -b --factory-startup --python (Join-Path $PSScriptRoot "smoke_blender.py")
exit $LASTEXITCODE
