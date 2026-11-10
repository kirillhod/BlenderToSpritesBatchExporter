param(
    [string]$Version
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$packageName = "blender_to_sprites_batch_exporter"
$packageDir = Join-Path $root $packageName
$manifestPath = Join-Path $packageDir "blender_manifest.toml"

if (-not (Test-Path $manifestPath)) {
    throw "Manifest not found: $manifestPath"
}

if (-not $Version) {
    $manifest = Get-Content -Raw -Encoding UTF8 $manifestPath
    if ($manifest -match '(?m)^version\s*=\s*"([^"]+)"') {
        $Version = $Matches[1]
    } else {
        throw "Could not read version from $manifestPath"
    }
}

$dist = Join-Path $root "dist"
New-Item -ItemType Directory -Force $dist | Out-Null
$zipPath = Join-Path $dist "$packageName-$Version.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::Open(
    $zipPath,
    [System.IO.Compression.ZipArchiveMode]::Create
)
try {
    Get-ChildItem $packageDir -Recurse -File | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'
    } | ForEach-Object {
        $relative = $_.FullName.Substring($packageDir.Length + 1).Replace('\', '/')
        $entryName = "$packageName/$relative"
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, $_.FullName, $entryName
        ) | Out-Null
    }
} finally {
    $zip.Dispose()
}

Write-Host "Built $zipPath"
