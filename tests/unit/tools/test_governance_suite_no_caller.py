"""The governance suite's local infrastructure tests on a repository the fleet now leaves bare.

T09 required `.github/workflows/pr-sentinel.yml` and `.github/workflows/auto-reviewer.yml`.
Both are retired: the pr-sentinel Worker posts the check, and the Auto Review caller calls a
reusable workflow whose every job is `if: false` (#3663, #4719).

T08 required the per-repository Cerberus secrets `REVIEWER_APP_ID` and
`REVIEWER_APP_PRIVATE_KEY`. Nothing reads them since Auto Review's retirement: the Worker
approves as Cerberus with its own copy of the key (#4724). A repository with no workflow file
and no Cerberus secret must pass the infrastructure tests, and the suite must not ask GitHub
for either.

The suite's I/O boundaries (`run_gh`, `run_curl`) are replaced; nothing reaches GitHub.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3] / "tools"


def _load_suite(monkeypatch):
    # Loaded under another name so pytest does not take the tool for a test module. The
    # module is registered first: its dataclass resolves annotations through sys.modules.
    name = "governance_suite"
    spec = importlib.util.spec_from_file_location(name, TOOLS / "test_governance_system.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, mod)
    spec.loader.exec_module(mod)
    return mod


def test_a_repository_without_workflows_or_cerberus_secrets_passes_the_infrastructure_tests(
    monkeypatch, capsys
):
    gov = _load_suite(monkeypatch)
    asked: list[tuple[str, ...]] = []

    def fake_gh(*args, timeout=30, stdin=None):
        asked.append(args)
        if args[:2] == ("secret", "list"):
            return 0, ""  # the repository holds no secret at all
        if args and args[0] == "api" and "/contents/.github/workflows/" in args[1]:
            return 1, "gh: Not Found (HTTP 404)"
        raise AssertionError(f"unexpected gh call {args}")

    monkeypatch.setattr(gov, "run_gh", fake_gh)
    monkeypatch.setattr(gov, "run_curl", lambda url, timeout=10: (200, "ok"))

    results = gov.run_local_tests("o/bare", dry_run=True)

    failed = [(r.test_id, r.actual) for r in results if not r.passed]
    assert failed == []
    assert [r.test_id for r in results] == ["T07"]
    assert not any("workflows" in " ".join(a) for a in asked)
    assert not any(a[:1] == ("secret",) for a in asked), "the suite listed the repository's secrets"
    assert "Cerberus secrets" not in capsys.readouterr().out


def test_the_retired_checks_are_gone_from_the_suite(monkeypatch):
    gov = _load_suite(monkeypatch)
    assert not hasattr(gov, "test_workflow_files")
    assert not hasattr(gov, "test_cerberus_secrets")
