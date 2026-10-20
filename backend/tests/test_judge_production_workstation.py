"""Phase 17 regression: the Windows judge rehearsal must actually run offline checks.

The browser suite itself is executed against the running production site by CI;
this test protects the PowerShell entrypoint so it cannot quietly fall back to
the earlier journey-only rehearsal.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts" / "Start-KaushalWatch-Judge.ps1"
OFFLINE_SPEC = ROOT / "web" / "e2e" / "phase16-offline-branded.spec.ts"
JOURNEY_SPEC = ROOT / "web" / "e2e" / "phase15-release-rehearsal.spec.ts"


def test_production_rehearsal_runs_journey_plus_real_offline_browser_suite():
    script = LAUNCHER.read_text(encoding="utf-8")
    assert JOURNEY_SPEC.is_file() and OFFLINE_SPEC.is_file()
    assert re.search(
        r"\$rehearsalSpecs\s*=\s*@\('e2e/phase15-release-rehearsal\.spec\.ts'\)"
        r"\s*if\(\$ProductionWeb\)\s*\{"
        r"\s*\$rehearsalSpecs\s*\+=\s*'e2e/phase16-offline-branded\.spec\.ts'",
        script,
    )
    assert re.search(
        r"& \$node \$playwrightCli test @rehearsalSpecs "
        r"'--project=chromium' '--workers=1' '--reporter=line'",
        script,
    )
    assert "if($LASTEXITCODE -ne 0){" in script
    assert "OFFLINE BROWSER PASSED" in script
    assert re.search(r"if\(\$ProductionWeb\)\s*\{\s*Write-Host 'OFFLINE BROWSER PASSED", script)


def test_offline_suite_blocks_external_requests_and_proves_real_local_assets():
    source = OFFLINE_SPEC.read_text(encoding="utf-8")
    for signal in [
        "page.route('**/*'",
        "internetdisconnected",
        "document.fonts.ready",
        "Poppins",
        "Bricolage",
        "Manifest hash matched",
        "Officer evidence chain",
        "/report.pdf",
        "320px Insights",
    ]:
        assert signal in source, signal


def test_rehearsal_still_fails_closed_and_cleans_only_spawned_processes():
    script = LAUNCHER.read_text(encoding="utf-8")
    assert "throw 'Controlled browser rehearsal FAILED" in script
    assert "-PreflightOnly and -RunRehearsal cannot be combined." in script
    assert "if($web -and -not $web.HasExited){Stop-Process -Id $web.Id -Force}" in script
    assert "if($api -and -not $api.HasExited){Stop-Process -Id $api.Id -Force}" in script
    assert "scripts/check_judge_runtime.py') --api-port $ApiPort --web-port $WebPort --once" in script
