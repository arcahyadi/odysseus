#Requires -Version 5.1
<#
  Build a portable Windows distribution for Odysseus.

  Two output flavours:

    onedir (default)
      dist\Odysseus\Odysseus.exe
      dist\Odysseus\_internal\...     <- runtime + bundled payload

    -OneFile
      dist\standalone\Odysseus.exe    <- one self-contained exe

  PyInstaller 6 keeps everything except the exe inside _internal\, including the
  --add-data payload (static, scripts, mcp_servers, services/hwfit/data, config,
  .env.example). An onedir build is therefore only portable as a whole folder.

  A -OneFile build is a single exe that unpacks its own runtime to a temp
  directory at launch: nothing has to sit next to it. Startup is slower (the
  unpack repeats every launch) but it is the flavour that can simply be
  double-clicked from anywhere.

  Whichever flavour is built, a runnable copy is refreshed at the repo root:
    Odysseus.exe
    _internal\      (onedir only - junction -> dist\Odysseus\_internal)
  See scripts\link-root-launcher.ps1 for why that step is needed.

  Usage:
    powershell -ExecutionPolicy Bypass -File .\build-windows-portable.ps1
    powershell -ExecutionPolicy Bypass -File .\build-windows-portable.ps1 -OneFile
#>
param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Write-Step($msg) { Write-Host ""; Write-Host ("==> " + $msg) -ForegroundColor Cyan }
function Fail($msg) {
    Write-Host ""
    Write-Host ("ERROR: " + $msg) -ForegroundColor Red
    exit 1
}

Write-Step "Checking for Python"
$pyExe = $null
if (Test-Path ".\.venv\Scripts\python.exe") {
    $pyExe = (Resolve-Path ".\.venv\Scripts\python.exe").Path
} else {
    foreach ($c in @("py", "python")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { $pyExe = $cmd.Source; break }
    }
    if ($pyExe -like "*WindowsApps*python.exe") {
        $pyCmd = Get-Command py -ErrorAction SilentlyContinue
        if ($pyCmd) {
            $pyExe = $pyCmd.Source
        }
    }
}
if (-not $pyExe) {
    Fail "Python not found on PATH. Install Python 3.11+ first."
}
Write-Host ("Using Python: " + $pyExe)

Write-Step "Installing build dependencies"
& $pyExe -m pip install --upgrade pip --quiet
& $pyExe -m pip install -r requirements.txt pyinstaller pystray Pillow --quiet
if ($LASTEXITCODE -ne 0) { Fail "Dependency install failed." }

Write-Step "Building portable exe bundle"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

$dataArgs = @(
    "--add-data", "static;static",
    "--add-data", "scripts;scripts",
    "--add-data", "mcp_servers;mcp_servers",
    "--add-data", "services/hwfit/data;services/hwfit/data",
    "--add-data", "config;config",
    "--add-data", ".env.example;.env.example"
)

if ($OneFile) {
    # A distinct --distpath keeps this from colliding with the onedir output:
    # PyInstaller removes its output directory by name, so sharing dist\Odysseus
    # would delete the onedir bundle (and any root junction aimed at it).
    & $pyExe -m PyInstaller --noconfirm --clean --onefile --noconsole --icon=static/icon.ico --distpath dist/standalone --name Odysseus @dataArgs launcher.py
    if ($LASTEXITCODE -ne 0) { Fail "PyInstaller build failed." }

    Write-Step "Refreshing root launcher (standalone Odysseus.exe)"
    try {
        & (Join-Path $PSScriptRoot "scripts\link-root-launcher.ps1") -StandaloneExe "dist\standalone\Odysseus.exe"
    }
    catch {
        Write-Host ("  WARNING: could not refresh root launcher: " + $_.Exception.Message) -ForegroundColor Yellow
        Write-Host "  The build itself succeeded - run scripts\link-root-launcher.ps1 -StandaloneExe dist\standalone\Odysseus.exe manually to fix." -ForegroundColor Yellow
    }
}
else {
    & $pyExe -m PyInstaller --noconfirm --clean --onedir --noconsole --icon=static/icon.ico --name Odysseus @dataArgs launcher.py
    if ($LASTEXITCODE -ne 0) { Fail "PyInstaller build failed." }

    Write-Step "Refreshing root launcher (Odysseus.exe + _internal junction)"
    try {
        & (Join-Path $PSScriptRoot "scripts\link-root-launcher.ps1")
    }
    catch {
        Write-Host ("  WARNING: could not refresh root launcher: " + $_.Exception.Message) -ForegroundColor Yellow
        Write-Host "  The build itself succeeded - run scripts\link-root-launcher.ps1 manually to fix." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
if ($OneFile) {
    Write-Host "Standalone exe : $PSScriptRoot\dist\standalone\Odysseus.exe" -ForegroundColor Green
    Write-Host "Root launcher  : $PSScriptRoot\Odysseus.exe (self-contained)" -ForegroundColor Green
    Write-Host "Distribute the exe on its own - it needs nothing alongside it." -ForegroundColor Green
}
else {
    Write-Host "Portable app folder: $PSScriptRoot\dist\Odysseus" -ForegroundColor Green
    Write-Host "Distribute the whole folder (or zip it) so static assets and scripts stay with the exe." -ForegroundColor Green
}
