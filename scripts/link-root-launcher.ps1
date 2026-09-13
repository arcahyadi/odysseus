#Requires -Version 5.1
<#
.SYNOPSIS
    Refresh the repo-root copy of the portable Windows build so it stays runnable.

.DESCRIPTION
    Keeps a runnable copy of the app at the repo root, in whichever flavour the
    build produced.

    onedir mode (default): Odysseus.exe resolves its payload from an `_internal`
    directory sitting next to the exe, so this script
        1. copies dist\Odysseus\Odysseus.exe to the repo root, and
        2. points a root-level `_internal` directory junction at
           dist\Odysseus\_internal (a junction avoids duplicating ~180 MB).

    onefile mode (-StandaloneExe): the exe is self-contained and unpacks its own
    runtime to a temp directory at launch, so there is nothing to point at. This
    script copies the exe to the root and removes any `_internal` junction left
    over from an earlier onedir build.

    Run this after every rebuild: build-windows-portable.ps1 deletes dist/, and
    dist/ holds the junction target. That script calls this automatically at the
    end of a build - you only need it by hand to repair a root launcher.

    This only affects a local working copy: the root exe and the _internal
    junction are gitignored and never leave the machine.

.PARAMETER RepoRoot
    Repository root. Defaults to the parent directory of this script.

.PARAMETER DistDir
    Path to the onedir output, relative to RepoRoot. Default: dist\Odysseus

.PARAMETER StandaloneExe
    Path to a --onefile build, relative to RepoRoot. When supplied, takes
    precedence over DistDir and the root launcher becomes that single exe.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\link-root-launcher.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\link-root-launcher.ps1 -StandaloneExe "dist\standalone\Odysseus.exe"
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$DistDir = "dist\Odysseus",
    [string]$StandaloneExe = ""
)

$ErrorActionPreference = "Stop"

$distExe = Join-Path $RepoRoot (Join-Path $DistDir "Odysseus.exe")
$distInternal = Join-Path $RepoRoot (Join-Path $DistDir "_internal")
$rootExe = Join-Path $RepoRoot "Odysseus.exe"
$rootInternal = Join-Path $RepoRoot "_internal"

# ── Standalone (--onefile) mode ────────────────────────────────────────────
# A onefile build honours no sibling folder, so there is nothing to point at.
# Drop any junction left over from an earlier onedir build: it would otherwise
# be dead weight aimed at a payload that nothing reads.
if ($StandaloneExe) {
    $srcExe = Join-Path $RepoRoot $StandaloneExe
    if (-not (Test-Path $srcExe)) {
        throw "Missing standalone build output: $srcExe"
    }

    if (Test-Path $rootInternal) {
        cmd /c rmdir "$rootInternal" | Out-Null
        Write-Host "  Removed stale _internal junction (a onefile build does not use it)."
    }

    Copy-Item -Path $srcExe -Destination $rootExe -Force
    Write-Host "  Root exe (standalone) : $rootExe"
    Write-Host "  Source                : $srcExe"
    Write-Host "  Root launcher ready."
    return
}

if (-not (Test-Path $distExe)) {
    throw "Missing build output: $distExe"
}
if (-not (Test-Path $distInternal)) {
    throw "Missing runtime directory: $distInternal"
}

# Replace any existing root junction.
#
# SECURITY / SAFETY: `cmd /c rmdir` deletes ONLY the reparse point itself.
# `Remove-Item -Recurse` follows the junction and would delete the real payload
# inside dist/ - do not "simplify" this to Remove-Item.
if (Test-Path $rootInternal) {
    cmd /c rmdir "$rootInternal" | Out-Null
    if (Test-Path $rootInternal) {
        throw "Could not remove existing junction: $rootInternal"
    }
}

Copy-Item -Path $distExe -Destination $rootExe -Force
New-Item -ItemType Junction -Path $rootInternal -Target $distInternal | Out-Null

Write-Host "  Root exe         : $rootExe"
Write-Host "  Runtime junction : $rootInternal -> $distInternal"
Write-Host "  Root launcher ready."
