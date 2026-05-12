"""Tests for tools/land_1131_auto_reviewer_skip_dependabot.py (#1131)."""
import importlib.util
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_spec = importlib.util.spec_from_file_location(
    "land_1131_auto_reviewer_skip_dependabot",
    TOOLS_DIR / "land_1131_auto_reviewer_skip_dependabot.py",
)
land = importlib.util.module_from_spec(_spec)
sys.modules["land_1131_auto_reviewer_skip_dependabot"] = land
_spec.loader.exec_module(land)


def test_apply_patch_against_current_workflow_file_produces_diff():
    """End-to-end smoke: read the live auto-reviewer.yml and patch it."""
    local = TOOLS_DIR.parent / ".github" / "workflows" / "auto-reviewer.yml"
    assert local.is_file(), \
        f"workflow file missing at {local} -- can't smoke-test the patch"
    content = local.read_text(encoding="utf-8", errors="replace")
    patched = land.apply_patch(content)
    assert patched is not None, \
        "patch should apply -- file may already contain the #1131 change"
    assert "dependabot[bot]" in patched
    assert "#1131" in patched


def test_apply_patch_idempotent_on_already_patched():
    already = "anything with #1131 and dependabot[bot] sentinel"
    assert land.apply_patch(already) is None


def test_apply_patch_aborts_on_drift_when_old_if_missing():
    """If the source file has drifted (the old `if:` line no longer matches),
    refuse to apply rather than write nonsense."""
    drifted = "completely different workflow structure with no matching if:"
    import pytest
    with pytest.raises(SystemExit):
        land.apply_patch(drifted)


def test_old_if_string_matches_actual_workflow_file():
    """The OLD_IF byte-string in the script must literally appear in the
    current auto-reviewer.yml. If it doesn't, the script is broken before
    a single API call is made."""
    local = TOOLS_DIR.parent / ".github" / "workflows" / "auto-reviewer.yml"
    content = local.read_text(encoding="utf-8", errors="replace")
    assert land.OLD_IF in content, \
        "OLD_IF doesn't match -- workflow file has drifted, patch will fail"


def test_new_if_contains_required_dependabot_skip_clause():
    assert "dependabot[bot]" in land.NEW_IF
    assert "pull_request.user.login" in land.NEW_IF
    # Comment reference makes the intent traceable
    assert "#1131" in land.NEW_IF
