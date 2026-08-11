"""Tests for tools/_npm_manifest.py — the npm test-script guard (#2182).

The guard exists because a repo could be born receiving npm dependabot PRs it
was structurally incapable of passing review on. The review gate (#1839)
refuses to merge an npm PR whose directory has no runnable `test` script, and
nothing on the enabling side checked for one.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import _npm_manifest as npm  # noqa: E402


def _pkg(d: Path, scripts=None, lock="package-lock.json"):
    d.mkdir(parents=True, exist_ok=True)
    body = {"name": d.name}
    if scripts is not None:
        body["scripts"] = scripts
    (d / "package.json").write_text(json.dumps(body), encoding="utf-8")
    if lock:
        (d / lock).write_text("{}", encoding="utf-8")
    return d


# ---- npm_test_script: what counts as runnable ----

def test_real_script_is_runnable(tmp_path):
    d = _pkg(tmp_path / "a", {"test": "vitest run"})
    assert npm.npm_test_script(d) == "vitest run"


def test_npm_init_placeholder_does_not_count(tmp_path):
    """The subtle one, and the reason this cannot be a truthiness check.

    Running the placeholder exits 1 with a message that would be misreported
    as a test failure, when the real condition is "declares no tests".
    """
    d = _pkg(tmp_path / "a",
             {"test": 'echo "Error: no test specified" && exit 1'})
    assert npm.npm_test_script(d) is None


@pytest.mark.parametrize("scripts", [None, {}, {"test": ""}, {"test": "   "},
                                     {"test": 42}, {"build": "vite build"}])
def test_absent_empty_or_non_string_is_not_runnable(tmp_path, scripts):
    d = _pkg(tmp_path / "a", scripts)
    assert npm.npm_test_script(d) is None


def test_unreadable_manifest_is_conservative(tmp_path):
    """Cannot evaluate means report as missing — prompts a look, never a pass."""
    d = tmp_path / "a"
    d.mkdir()
    (d / "package.json").write_text("{ not json", encoding="utf-8")
    assert npm.npm_test_script(d) is None


def test_missing_manifest_is_not_runnable(tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    assert npm.npm_test_script(d) is None


# ---- find_npm_manifests: which directories can receive npm PRs ----

def test_a_lockfile_is_what_makes_a_directory_reachable(tmp_path):
    _pkg(tmp_path / "withlock", {"test": "x"})
    _pkg(tmp_path / "nolock", {"test": "x"}, lock=None)
    found = npm.find_npm_manifests(tmp_path)
    assert found == [tmp_path / "withlock"]


@pytest.mark.parametrize("lock", ["package-lock.json", "npm-shrinkwrap.json",
                                  "yarn.lock", "pnpm-lock.yaml"])
def test_every_lockfile_flavour_counts(tmp_path, lock):
    _pkg(tmp_path / "a", {"test": "x"}, lock=lock)
    assert npm.find_npm_manifests(tmp_path) == [tmp_path / "a"]


def test_node_modules_is_never_descended(tmp_path):
    """Vendored manifests are not ours; thousands of them would swamp output."""
    _pkg(tmp_path / "app", {"test": "x"})
    _pkg(tmp_path / "app" / "node_modules" / "left-pad", None)
    assert npm.find_npm_manifests(tmp_path) == [tmp_path / "app"]


def test_subdirectories_are_covered_not_just_the_root(tmp_path):
    """The observed failure was a subdirectory the root said nothing about."""
    _pkg(tmp_path, {"test": "x"})
    _pkg(tmp_path / "dashboard", None)
    assert (tmp_path / "dashboard") in npm.find_npm_manifests(tmp_path)


# ---- dirs_missing_test_script: the reportable answer ----

def test_reports_dependabot_style_paths(tmp_path):
    _pkg(tmp_path, None)                        # root, no script
    _pkg(tmp_path / "dashboard", None)          # subdir, no script
    _pkg(tmp_path / "sentinel", {"test": "vitest run"})   # compliant
    assert npm.dirs_missing_test_script(tmp_path) == ["/", "/dashboard"]


def test_compliant_repo_reports_nothing(tmp_path):
    _pkg(tmp_path, {"test": "pytest"})
    _pkg(tmp_path / "web", {"test": "vitest run"})
    assert npm.dirs_missing_test_script(tmp_path) == []


def test_placeholder_directory_is_reported(tmp_path):
    _pkg(tmp_path / "web", {"test": 'echo "Error: no test specified" && exit 1'})
    assert npm.dirs_missing_test_script(tmp_path) == ["/web"]


# ---- drift: this must keep agreeing with the review gate ----

def test_agrees_with_the_review_gate_definition(tmp_path):
    """The two halves must not drift apart on what "runnable" means.

    Skips cleanly if the harvester is no longer in this repo — it is slated to
    move (see the migration tracked in the private fleet repo), and a
    hard-failing cross-import would turn that move into a broken build. When
    it does move, this skip is the signal to re-point the check.
    """
    spec = importlib.util.spec_from_file_location(
        "_dr_probe", TOOLS / "dependabot_review.py")
    if spec is None or not (TOOLS / "dependabot_review.py").exists():
        pytest.skip("dependabot_review.py not in this repo (migrated)")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cases = [
        {"test": "vitest run"},
        {"test": 'echo "Error: no test specified" && exit 1'},
        {"test": ""},
        {},
        None,
    ]
    for i, scripts in enumerate(cases):
        d = _pkg(tmp_path / f"c{i}", scripts)
        assert (npm.npm_test_script(d) is None) == (mod._npm_test_script(d) is None), (
            f"definitions disagree on {scripts!r}"
        )
