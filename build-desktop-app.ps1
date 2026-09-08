#Requires -Version 5.1
<#
.SYNOPSIS
    Build the Odysseus Desktop App - a single .exe that starts Docker Desktop,
    runs `docker compose up`, and opens the browser automatically.

.DESCRIPTION
    Produces:
        dist\OdysseusApp\OdysseusApp.exe   - double-click to launch

    The exe is self-contained: it ships with the launcher script and the tray/
    splash assets. Everything else (docker-compose.yml, static/, data/, .env)
    must live ALONGSIDE the exe, so distribute the whole project folder.

    Before building, optionally place your icon files:
        static\icon.ico   - used for the .exe file icon (Windows Explorer / taskbar)
        static\icon.png   - used for the system-tray icon at runtime

.USAGE
    powershell -ExecutionPolicy Bypass -File .\build-desktop-app.ps1

.NOTES
    Requirements: Python 3.11+, pip
    The script installs PyInstaller, Pillow, and pystray automatically.
#>

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step($msg) {
    Write-Host ""
    Write-Host ("==> " + $msg) -ForegroundColor Cyan
}
function Fail($msg) {
    Write-Host ""
    Write-Host ("ERROR: " + $msg) -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Locate Python
# ---------------------------------------------------------------------------
Write-Step "Locating Python"

$pyExe = $null

# Prefer the project venv if it exists
if (Test-Path ".\.venv\Scripts\python.exe") {
    $pyExe = (Resolve-Path ".\.venv\Scripts\python.exe").Path
    Write-Host "  Using project venv: $pyExe"
} else {
    foreach ($candidate in @("py", "python", "python3")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            # Skip the Windows Store stub (it does nothing useful)
            if ($cmd.Source -notlike "*WindowsApps*") {
                $pyExe = $cmd.Source
                break
            }
        }
    }
    # Second chance: py.exe launcher may point to a real interpreter
    if (-not $pyExe) {
        $pyCmd = Get-Command py -ErrorAction SilentlyContinue
        if ($pyCmd) { $pyExe = $pyCmd.Source }
    }
}

if (-not $pyExe) {
    Fail "Python 3.11+ not found. Install it from https://python.org and ensure it is on PATH."
}
Write-Host "  Python: $pyExe"

# ---------------------------------------------------------------------------
# Install build-time dependencies
# ---------------------------------------------------------------------------
Write-Step "Installing build dependencies (PyInstaller, Pillow, pystray)"

& $pyExe -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed." }

& $pyExe -m pip install --quiet pyinstaller pillow pystray
if ($LASTEXITCODE -ne 0) { Fail "Dependency install failed." }

# ---------------------------------------------------------------------------
# Resolve icon paths
# ---------------------------------------------------------------------------
Write-Step "Resolving icon"

$icoPath = $null
$icoArg  = @()

$candidates = @(
    "static\icon.ico",
    "static\icon.png"    # PyInstaller accepts PNG on non-macOS too
)
foreach ($c in $candidates) {
    if (Test-Path $c) {
        $icoPath = (Resolve-Path $c).Path
        break
    }
}

if ($icoPath) {
    Write-Host "  Icon: $icoPath"
    $icoArg = @("--icon", $icoPath)
} else {
    Write-Host "  No icon found at static\icon.ico or static\icon.png - exe will use the default Python icon." -ForegroundColor Yellow
    Write-Host "  Drop your icon file there before building to brand the exe."
}

# ---------------------------------------------------------------------------
# Clean previous build artefacts
# ---------------------------------------------------------------------------
Write-Step "Cleaning previous build"

foreach ($dir in @("build", "dist\OdysseusApp")) {
    if (Test-Path $dir) {
        Remove-Item -Recurse -Force $dir
        Write-Host "  Removed $dir"
    }
}

# ---------------------------------------------------------------------------
# Build with PyInstaller
# ---------------------------------------------------------------------------
Write-Step "Building OdysseusApp.exe with PyInstaller"

#  --onedir      : single folder (faster startup than --onefile, better for
#                  antivirus compatibility)
#  --noconsole   : no black cmd window on double-click
#  --name        : output name
#  --add-data    : bundle the tray icon so it works from the frozen exe

$addDataArgs = @()

# Bundle static assets that the frozen launcher needs at runtime
foreach ($asset in @("static/icon.ico", "static/icon.png")) {
    if (Test-Path $asset) {
        $abs = (Resolve-Path $asset).Path
        $addDataArgs += "--add-data"
        $addDataArgs += "${abs};static"
    }
}

$pyinstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--onedir",
    "--noconsole",
    "--name", "OdysseusApp"
) + $icoArg + $addDataArgs + @("launcher_docker.py")

Write-Host ""
Write-Host "  pyinstaller $($pyinstallerArgs -join ' ')" -ForegroundColor DarkGray

& $pyExe -m PyInstaller @pyinstallerArgs
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller build failed." }

# ---------------------------------------------------------------------------
# Post-build: copy companion files into the dist folder
# ---------------------------------------------------------------------------
Write-Step "Copying companion files into dist\OdysseusApp"

$distDir = "dist\OdysseusApp"

# Files / folders that must live alongside the exe so the launcher can find them
$companions = @(
    "docker-compose.yml",
    ".env.example"
)
# Optional - copy if present
$optionals = @(
    ".env",
    "docker-compose.gpu-nvidia.yml",
    "docker-compose.gpu-amd.yml",
    "config"
)

foreach ($f in $companions) {
    if (Test-Path $f) {
        Copy-Item -Recurse -Force $f "$distDir\"
        Write-Host "  Copied $f"
    } else {
        Write-Host "  WARNING: $f not found - skipping." -ForegroundColor Yellow
    }
}
foreach ($f in $optionals) {
    if (Test-Path $f) {
        Copy-Item -Recurse -Force $f "$distDir\"
        Write-Host "  Copied $f (optional)"
    }
}

# Create empty data/ and logs/ placeholders so the launcher can write logs
foreach ($d in @("$distDir\data\logs", "$distDir\logs")) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
Write-Host "  Created data/ and logs/ placeholders"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host " Build complete!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host " Executable : $PSScriptRoot\$distDir\OdysseusApp.exe"
Write-Host " Distribute : the entire  dist\OdysseusApp\  folder"
Write-Host "              (the exe needs docker-compose.yml alongside it)"
Write-Host ""
Write-Host " TIP: Drop your icon as  static\icon.ico  (and static\icon.png"
Write-Host "      for the tray) then re-run this script to brand the exe."
Write-Host ""
