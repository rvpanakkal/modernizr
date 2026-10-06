# =============================================================================
# test_architecture_harvesting.ps1 -- Verification & Demonstration Runner
# =============================================================================
# Executes test suite for Target Architecture Provider Subsystem and runs
# a live demonstration harvesting samples/reference-spring-boot-service.
# =============================================================================

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$RepoRoot\modules\pipeline-core")) {
    $RepoRoot = $PSScriptRoot
}

$env:PYTHONPATH = "$RepoRoot\modules\pipeline-core"
$env:MOCK_MODE = "true"
$env:MOCK_LLM = "true"

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "   TARGET ARCHITECTURE PROVIDER SUBSYSTEM -- TEST & DEMO RUNNER     " -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

Write-Host "`n[1/2] Running Pytest Verification Suite..." -ForegroundColor Yellow
python -m pytest "$RepoRoot\modules\pipeline-core\tests\test_architecture_harvester.py" -v

Write-Host "`n[2/2] Running CLI Demonstration: Harvesting Reference Microservice..." -ForegroundColor Yellow
$demoScript = @"
import json
from pathlib import Path
from pipeline_core.architecture import (
    ReferenceMicroserviceProvider,
    get_architecture_registry,
    render_archunit_test_class,
)

repo_root = Path(r'$RepoRoot')
sample_dir = repo_root / 'samples' / 'reference-spring-boot-service'

print(f'-> Ingesting reference repository: {sample_dir}')
harvester = ReferenceMicroserviceProvider()
profile = harvester.build_profile(
    source_path_or_uri=str(sample_dir),
    profile_name='Enterprise Reference Payments & Accounts Microservice',
    profile_id='arch-payments-v2',
)

registry = get_architecture_registry()
saved_path = registry.save_profile(profile)
registry.set_active_profile(profile.profile_id)

print(f' [OK] Profile Harvested Successfully:')
print(f'      - Profile ID:           {profile.profile_id}')
print(f'      - Target Runtime:       {profile.target_runtime}')
print(f'      - Layering Style:       {profile.layering_pattern.value}')
print(f'      - Base Package Pattern: {profile.base_package_pattern}')
print(f'      - SHA-256 Checksum:     {profile.sha256_hash}')
print(f'      - Dependencies Count:   {len(profile.required_dependencies)}')
print(f'      - Exemplars Harvested:  {len(profile.exemplars)} ({[e.pattern_name for e in profile.exemplars]})')
print(f'      - ArchUnit Rules:       {len(profile.conformance_rules)} ({[r.rule_id for r in profile.conformance_rules]})')
print(f'      - Persisted To:         {saved_path}')

print('\n-> Generating Sample Step 5.5 ArchUnit Conformance Test Class...')
test_code = render_archunit_test_class(profile, package_name='com.enterprise.modernization')
print('---------------------------------------------------------------------')
print('\n'.join(test_code.splitlines()[:28]))
print('      [... ArchRule definitions ...]')
print('---------------------------------------------------------------------')
print(' [OK] Architecture Profile Subsystem is fully operational.')
"@

python -c $demoScript

Write-Host "`n=====================================================================" -ForegroundColor Green
Write-Host "   HARVESTING VERIFICATION & DEMONSTRATION COMPLETE                  " -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Green
