"""A large file is changed in place by edit script, never asked for whole (#4683).

An implementation run against a TypeScript target halted on iteration 0, file
3 of 8: a 3,666-line, 171,540-byte module, which N4 asked for as "the COMPLETE
file contents". Both attempts came back as the one new function the spec
asked for, and the size gate (#587) refused them, rightly: a fragment written
over a whole file is the truncation it exists to stop. The edit script (#2407)
never engaged, because it is chosen only when there is a failure to fix.

These tests drive `implement_code` with the model call stubbed, as
`test_failed_patch_on_a_test_file_leaves_it.py` does, and assert the decisions:
which path a file takes, what the prompt carries, and what happens when no
edit script holds.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.implementation import (
    claude_client,
    edit_script_fix,
    orchestrator,
)
from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
    ImplementationError,
)
from assemblyzero.workflows.testing.nodes.implementation.unrequested_changes import (
    spec_subsection,
)

PAD = "#" * 60
#: Over LARGE_FILE_CHARS: 800 numbered lines of about 75 characters, then the
#: one function the spec changes.
BIG = "".join(f"VALUE_{i:04d} = {i}  {PAD}\n" for i in range(800)) + (
    "\n\ndef value():\n    return 0\n"
)
SMALL = "# " + ("x" * 900) + "\n" + "def value():\n    return 0\n"

SPEC = """\
## 5. Function Specifications

Nothing here is a Section 6 heading.

## 6. Change Instructions

### 6.1 `src/pkg/big.py` (Modify)

Add `new_value()` beside `value()`.

```diff
@@ -801,2 +801,6 @@
 def value():
     return 0
+
+
+def new_value():
+    return 1
## this line is inside a fence and ends nothing
```

### 6.2 `src/pkg/small.py` (Modify)

MARKER_SMALL: the other file's instructions.

## 7. Pattern References
"""

PATCH = """\
<<<<<<< SEARCH
def value():
    return 0
=======
def value():
    return 0


def new_value():
    return 1
>>>>>>> REPLACE
"""

MISSES = """\
<<<<<<< SEARCH
def not_in_the_file():
    pass
=======
def not_in_the_file():
    return 1
>>>>>>> REPLACE
"""

#: Removes the first 600 of the file's 803 lines: under half remains.
SHRINK = (
    "<<<<<<< SEARCH\n"
    + "".join(f"VALUE_{i:04d} = {i}  {PAD}\n" for i in range(600))
    + "=======\n"
    + ">>>>>>> REPLACE\n"
)


class FakeModel:
    """Stands in for ``call_claude_for_file``: queued replies, the last repeated."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def __call__(self, prompt="", file_path="", seat=None, system_prompt="", **kw):
        self.prompts.append(prompt)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return reply, ""


@pytest.fixture(autouse=True)
def no_transport(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("a real model transport was reached")

    monkeypatch.setattr(claude_client, "get_provider", refuse)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "big.py").write_text(BIG, encoding="utf-8")
    (tmp_path / "src" / "pkg" / "small.py").write_text(SMALL, encoding="utf-8")
    (tmp_path / "tests" / "unit" / "test_big.py").write_text(
        BIG + "\n\ndef test_value():\n    assert value() == 1\n", encoding="utf-8"
    )
    return tmp_path


def _run(repo, model, files, iteration=0, failures="", rewritten=None):
    """Run N4 once; return the files sent to the whole-file path.

    ``rewritten`` is the caller's list when N4 is expected to raise, so what
    it recorded before raising can still be read.
    """
    rewritten = [] if rewritten is None else rewritten

    def fake_rewrite(filepath, **kwargs):
        rewritten.append(filepath)
        return "def value():\n    return 1\n", True

    state = {
        "repo_root": str(repo),
        "lld_content": SPEC,
        "files_to_modify": files,
        "test_files": ["tests/unit/test_big.py"],
        "iteration_count": iteration,
        "test_failure_summary": failures,
        "audit_dir": str(repo / "audit"),
    }
    # The base ships every file here. The tmp tree is not a repo, so git's
    # answer is what is stood in for, as test_edit_script_reaches_the_mid_arc_fix
    # does: stubbing the skip or the change-type resolution would stub the subject.
    with patch.object(orchestrator, "came_from_base", return_value=True), \
         patch.object(orchestrator, "call_claude_for_file", model), \
         patch.object(orchestrator, "generate_file_with_retry", fake_rewrite), \
         patch.object(orchestrator, "validate_files_to_modify", return_value=[]), \
         patch.object(orchestrator, "record_iteration_cost", return_value=0), \
         patch.object(orchestrator, "get_cumulative_cost", return_value=0.0):
        try:
            orchestrator.implement_code(state)
        except ImplementationError:
            raise
        except Exception:  # noqa: BLE001, S110 - as the #2866 harness does
            # Later bookkeeping is not under test; the per-file decisions
            # have been made and written by the time it runs.
            pass
    return rewritten


BIG_FILE = [{"path": "src/pkg/big.py", "change_type": "Modify", "description": "add new_value"}]


class TestTheThreshold:
    """T1: half the prompt cap, measured in characters."""

    def test_is_half_the_prompt_cap(self):
        assert edit_script_fix.LARGE_FILE_CHARS == orchestrator.CODE_GEN_PROMPT_CAP // 2

    def test_at_the_threshold_is_large(self):
        assert edit_script_fix.is_large_file("Modify", "x" * edit_script_fix.LARGE_FILE_CHARS)

    def test_one_under_is_not(self):
        assert not edit_script_fix.is_large_file(
            "Modify", "x" * (edit_script_fix.LARGE_FILE_CHARS - 1)
        )

    def test_an_add_is_never_large(self):
        assert not edit_script_fix.is_large_file("Add", "x" * 100_000)

    def test_the_fixture_is_large(self):
        assert edit_script_fix.is_large_file("Modify", BIG)
        assert not edit_script_fix.is_large_file("Modify", SMALL)


class TestTheDraftPrompt:
    """T2: the spec's change for this file, not a fix of failing tests."""

    def test_the_subsection_is_this_files_only(self):
        section = spec_subsection(SPEC, "src/pkg/big.py")

        assert section.startswith("### 6.1 `src/pkg/big.py`")
        assert "Add `new_value()`" in section
        assert "MARKER_SMALL" not in section
        assert "Pattern References" not in section

    def test_a_heading_inside_a_fence_ends_nothing(self):
        section = spec_subsection(SPEC, "src/pkg/big.py")

        assert "## this line is inside a fence and ends nothing" in section
        assert section.rstrip().endswith("```")

    def test_a_path_the_spec_does_not_name_has_no_subsection(self):
        assert spec_subsection(SPEC, "src/pkg/other.py") == ""

    def test_the_prompt_carries_the_spec_and_not_a_failure(self):
        prompt = edit_script_fix.build_code_edit_script_draft_prompt(
            filepath="src/pkg/big.py",
            existing_content=BIG,
            description="add new_value",
            spec_section=spec_subsection(SPEC, "src/pkg/big.py"),
        )

        assert "Implementation Request (edit script)" in prompt
        assert "Add `new_value()`" in prompt
        assert "<<<<<<< SEARCH" in prompt
        assert "Some tests fail" not in prompt
        assert "MARKER_SMALL" not in prompt


class TestALargeFileOnItsFirstDraft:
    """T3, T5, and the retry that recovers."""

    def test_is_patched_in_place_with_no_whole_file_call(self, repo, capsys):
        model = FakeModel(PATCH)

        rewritten = _run(repo, model, BIG_FILE)

        assert rewritten == []
        written = (repo / "src" / "pkg" / "big.py").read_text(encoding="utf-8")
        assert written.startswith(BIG.rstrip("\n"))
        assert "def new_value():\n    return 1" in written
        assert len(model.prompts) == 1
        assert "Implementation Request (edit script)" in model.prompts[0]
        assert "Add `new_value()`" in model.prompts[0]
        assert "[PRUNE]" not in capsys.readouterr().out

    def test_a_missed_anchor_is_retried_with_its_reason(self, repo):
        model = FakeModel(MISSES, PATCH)

        rewritten = _run(repo, model, BIG_FILE)

        assert rewritten == []
        assert len(model.prompts) == 2
        assert "YOUR PREVIOUS EDIT SCRIPT COULD NOT BE USED" in model.prompts[1]
        written = (repo / "src" / "pkg" / "big.py").read_text(encoding="utf-8")
        assert "def new_value():" in written

    def test_a_patch_that_deletes_most_of_it_meets_the_size_gate(self, repo):
        model = FakeModel(SHRINK, PATCH)

        _run(repo, model, BIG_FILE)

        assert len(model.prompts) == 2
        assert "Mechanical Size Gate" in model.prompts[1]
        written = (repo / "src" / "pkg" / "big.py").read_text(encoding="utf-8")
        assert written.count("\n") > 800


class TestWhenNoEditScriptHolds:
    """T4: N4 stops, naming the file and every attempt, and never rewrites."""

    def test_stops_after_the_retry_budget(self, repo, operator_alerts):
        model = FakeModel(MISSES)

        with pytest.raises(ImplementationError) as raised:
            _run(repo, model, BIG_FILE)

        message = str(raised.value)
        assert "src/pkg/big.py" in message
        assert "too large to rewrite" in message
        assert "attempt 1:" in message and "attempt 2:" in message
        assert len(model.prompts) == orchestrator.MAX_FILE_RETRIES
        assert (repo / "src" / "pkg" / "big.py").read_text(encoding="utf-8") == BIG

    def test_never_takes_the_whole_file_path(self, repo, operator_alerts):
        model = FakeModel(MISSES)
        rewritten: list[str] = []

        with pytest.raises(ImplementationError):
            _run(repo, model, BIG_FILE, rewritten=rewritten)

        assert rewritten == []


class TestALargeTestFileInAFix:
    """T6: #2866 holds for a large test file whose patch never applies."""

    CORPUS = """\
test_value
    tests/unit/test_big.py:805: in test_value
    assert value() == 1
    E   assert 0 == 1
"""

    def test_is_left_byte_identical(self, repo, operator_alerts):
        before = (repo / "tests" / "unit" / "test_big.py").read_bytes()
        model = FakeModel(MISSES)

        rewritten = _run(
            repo, model,
            [{"path": "tests/unit/test_big.py", "change_type": "Modify"}],
            iteration=1, failures=self.CORPUS,
        )

        assert rewritten == []
        assert (repo / "tests" / "unit" / "test_big.py").read_bytes() == before
        assert len(model.prompts) == orchestrator.MAX_FILE_RETRIES
        assert any(
            "tests/unit/test_big.py" in a["what"] and "#2866" in a["consequence"]
            for a in operator_alerts
        ), operator_alerts


class TestASmallFileIsUnchanged:
    """T7: under the threshold, the first draft is still a whole file."""

    def test_takes_the_whole_file_path(self, repo):
        model = FakeModel(PATCH)

        rewritten = _run(
            repo, model,
            [{"path": "src/pkg/small.py", "change_type": "Modify", "description": "x"}],
        )

        assert rewritten == ["src/pkg/small.py"]
        assert model.prompts == []
