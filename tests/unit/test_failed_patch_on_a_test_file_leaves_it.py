"""A failed patch on a planned TEST file leaves the file unchanged (#2866).

boostgauge #4, runs 19 and 20: the green loop measured 44/47 at 91 %, then
41/44 at 89 %, then 37/41 at 82 %. Six tests disappeared in two iterations.
Each time, the edit-script path on a planned test file failed -- `SEARCH text
not found (model did not copy verbatim)` -- and the loop fell back to full
regeneration of that file, as it does for any file. A regenerated test file
carries whatever tests the model wrote this time, not the ones that were
there. The freeze rule (#2064) never fired because the failing set changed
every iteration.

A test file that already exists is the contract the loop is measuring
against. A model that could not produce a verbatim anchor for it has not
earned a rewrite of it. Regeneration on a failed patch stays for
implementation files, where the file is the loop's own output.

Same harness as `test_failure_attribution_by_frame.py`: `implement_code`
driven with the model calls stubbed, so what is asserted is the decision.
"""

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.implementation import edit_script_fix
from assemblyzero.workflows.testing.nodes.implementation import orchestrator

BIG = "# " + ("x" * 900) + "\n"  # over MIN_BYTES_FOR_EDIT_SCRIPT

# Both files are named by the corpus, so both are attributed and both reach
# the edit-script path (the #2851 skip must not be what keeps them unchanged).
CORPUS = """\
test_a
    tests/unit/test_collector.py:10: in test_a
    assert collector.collect() == 1
    E   assert 0 == 1

test_b
    src/boostgauge/collector.py:5: in collect
    return 0
    E   AssertionError
"""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src" / "boostgauge").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "src" / "boostgauge" / "collector.py").write_text(BIG, encoding="utf-8")
    (tmp_path / "tests" / "unit" / "test_collector.py").write_text(BIG + "def test_a(): pass\n", encoding="utf-8")
    return tmp_path


def _run(repo, capsys, patch_failed: bool):
    regenerated: list[str] = []

    def failing_edit(filepath, **kwargs):
        if patch_failed:
            return edit_script_fix.EditScriptOutcome(
                None, failures=["block 1: SEARCH text not found"]
            )
        return edit_script_fix.EditScriptOutcome(kwargs["existing_content"], failures=[])

    def fake_regen(filepath, **kwargs):
        regenerated.append(filepath)
        return "# regenerated\n", True

    state = {
        "repo_root": str(repo),
        "lld_content": "## 2.1 Files\n",
        "files_to_modify": [
            {"path": "src/boostgauge/collector.py", "change_type": "Modify"},
            {"path": "tests/unit/test_collector.py", "change_type": "Modify"},
        ],
        "test_files": ["tests/unit/test_collector.py"],
        "iteration_count": 1,
        "test_failure_summary": CORPUS,
        "audit_dir": str(repo / "audit"),
    }
    with patch.object(orchestrator, "try_edit_script_fix", failing_edit), \
         patch.object(orchestrator, "generate_file_with_retry", fake_regen), \
         patch.object(orchestrator, "validate_files_to_modify", return_value=[]), \
         patch.object(orchestrator, "record_iteration_cost", return_value=0), \
         patch.object(orchestrator, "get_cumulative_cost", return_value=0.0):
        try:
            orchestrator.implement_code(state)
        except Exception:
            # Later bookkeeping is not under test; the per-file decisions
            # have been made and recorded by the time it runs.
            pass
    return regenerated, capsys.readouterr().out


class TestAFailedPatchOnATestFile:
    def test_does_not_regenerate_the_test_file(self, repo, capsys):
        regenerated, out = _run(repo, capsys, patch_failed=True)

        assert "tests/unit/test_collector.py" not in regenerated, regenerated
        assert "patch failed on a test file; left unchanged" in out

    def test_leaves_the_test_file_byte_identical(self, repo, capsys):
        before = (repo / "tests" / "unit" / "test_collector.py").read_bytes()

        _run(repo, capsys, patch_failed=True)

        assert (repo / "tests" / "unit" / "test_collector.py").read_bytes() == before

    def test_still_regenerates_an_implementation_file(self, repo, capsys):
        """The fallback is right where the file is the loop's own output."""
        regenerated, _ = _run(repo, capsys, patch_failed=True)

        assert "src/boostgauge/collector.py" in regenerated, regenerated


class TestASuccessfulPatchIsUnaffected:
    def test_no_regeneration_when_the_patch_applied(self, repo, capsys):
        regenerated, out = _run(repo, capsys, patch_failed=False)

        assert regenerated == [], regenerated
        assert "left unchanged" not in out
