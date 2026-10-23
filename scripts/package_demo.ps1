$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputDirectory = Join-Path $projectRoot "dist"
$archivePath = Join-Path $outputDirectory "ai-music-marketer-demo.zip"

if (Test-Path -LiteralPath $archivePath) {
    throw "Archive already exists: $archivePath. Move it before packaging again."
}

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$excludedDirectories = @(
    ".git",
    ".venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    "private-media",
    "dist",
    "coverage"
)
$archive = [System.IO.Compression.ZipFile]::Open(
    $archivePath,
    [System.IO.Compression.ZipArchiveMode]::Create
)

try {
    $files = Get-ChildItem -LiteralPath $projectRoot -File -Recurse -Force |
        Where-Object {
            $relativePath = $_.FullName.Substring($projectRoot.Length).TrimStart("\")
            $segments = $relativePath -split "[\\/]"
            $excludedPath = $false
            foreach ($segment in $segments) {
                if ($excludedDirectories -contains $segment) {
                    $excludedPath = $true
                    break
                }
            }
            $isLocalSecret = $_.Name -eq ".env" -or ($_.Name.StartsWith(".env.") -and $_.Name -ne ".env.example")
            $isLocalData = $_.Name -match "\.(db|sqlite|sqlite3)(-wal|-shm)?$" -or $_.Extension -in @(".pyc", ".log", ".tsbuildinfo")
            -not $excludedPath -and -not $isLocalSecret -and -not $isLocalData
        }

    foreach ($file in $files) {
        $entryName = $file.FullName.Substring($projectRoot.Length).TrimStart("\").Replace("\", "/")
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive,
            $file.FullName,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
}
finally {
    $archive.Dispose()
}

Write-Output "Created $archivePath"
