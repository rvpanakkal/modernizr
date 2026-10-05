# =============================================================================
# run_mock_mode.ps1 -- Modernization Factory Mock Mode Single-Click Launcher
# =============================================================================
Param(
    [string]$SourceDir = "samples\legacy-banking-monolith\src\main\java",
    [switch]$SkipJava = $false,
    [int]$BackendPort = 8000,
    [int]$UiPort = 5173
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

& "$RepoRoot\run_mock_mode.ps1" -SourceDir $SourceDir -SkipJava:$SkipJava -BackendPort $BackendPort -UiPort $UiPort
