"""Banned-command fleet sweep (#1808).

The classification IS the tool: a naive grep flags the guards and buries
the instructions — exactly backwards per the 0901 taxonomy. These tests
pin that instructors are findings, guards are not, and the walk never
strays beyond the two fixed globs.

Issue: #1808
"""

import importlib.util
import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "banned_command_sweep", TOOLS_DIR / "banned_command_sweep.py"
)
sweep_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sweep_mod)


def _repo(root: Path, name: str, commands: dict[str, str] | None = None,
          skills: dict[str, str] | None = None) -> Path:
    repo = root / name
    for sub, files in (("commands", commands or {}), ("skills", skills or {})):
        d = repo / ".claude" / sub
        d.mkdir(parents=True, exist_ok=True)
        for fname, text in files.items():
            (d / fname).write_text(text, encoding="utf-8")
    return repo


class TestClassification:

    def test_instruction_line_is_a_finding(self):
        line = "   - Auto-delete: `git -C /repo branch -D {branch-name}`"
        assert sweep_mod.classify_line(line) == "instructor"

    def test_prohibition_line_is_a_guard(self):
        line = "Delete via the ADR-0217 graft recipe — never `git branch -D` (banned)."
        assert sweep_mod.classify_line(line) == "guard"

    def test_refusal_wording_is_a_guard(self):
        line = "the driver already refuses `--admin`, `--no-verify`, and force-push"
        assert sweep_mod.classify_line(line) == "guard"


class TestSweep:

    def test_finds_instructor_and_excludes_guard(self, tmp_path):
        _repo(tmp_path, "landmine-repo", commands={
            "cleanup.md": (
                "# Cleanup\n"
                "Auto-delete: `git branch -D {branch}`\n"          # INSTRUCTOR
                "Do NOT use `git reset --hard` (banned).\n"        # GUARD
            ),
        })
        _repo(tmp_path, "clean-repo", commands={
            "cleanup.md": "Use `git branch -d` after the ADR-0217 graft.\n",
        })

        hits = sweep_mod.sweep(tmp_path)
        findings = [h for h in hits if h["class"] == "instructor"]
        guards = [h for h in hits if h["class"] == "guard"]

        assert len(findings) == 1
        assert findings[0]["repo"] == "landmine-repo"
        assert findings[0]["token"] == "git branch -D"
        assert len(guards) == 1
        assert guards[0]["token"] == "git reset --hard"

    def test_scans_skills_too(self, tmp_path):
        _repo(tmp_path, "skilled", skills={
            "merge.md": "Then run gh pr merge 5 --admin to finish.\n",
        })
        findings = [h for h in sweep_mod.sweep(tmp_path) if h["class"] == "instructor"]
        assert [h["token"] for h in findings] == ["gh --admin"]

    def test_never_strays_beyond_the_fixed_globs(self, tmp_path):
        repo = _repo(tmp_path, "sprawl")
        # Banned tokens OUTSIDE the scanned globs must be invisible.
        (repo / "README.md").write_text("git push --force is great\n", encoding="utf-8")
        docs = repo / ".claude" / "commands" / "nested"
        docs.mkdir()
        (docs / "deep.md").write_text("git branch -D x\n", encoding="utf-8")
        (repo / ".claude" / "commands" / "notes.txt").write_text(
            "git branch -D x\n", encoding="utf-8"
        )
        assert sweep_mod.sweep(tmp_path) == []

    def test_repos_without_claude_dirs_are_skipped(self, tmp_path):
        (tmp_path / "bare-repo").mkdir()
        assert sweep_mod.sweep(tmp_path) == []


class TestMain:

    def test_exit_1_and_report_on_findings(self, tmp_path, capsys):
        _repo(tmp_path, "landmine-repo", commands={
            "cleanup.md": "Auto-delete: `git branch -D {branch}`\n",
        })
        rc = sweep_mod.main(["--root", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "FINDINGS" in out
        assert "landmine-repo/cleanup.md:1" in out

    def test_exit_0_when_only_guards_exist(self, tmp_path, capsys):
        _repo(tmp_path, "walled", commands={
            "cleanup.md": "NEVER use `git branch -D` — banned.\n",
        })
        rc = sweep_mod.main(["--root", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "No banned-command instructions found" in out
        assert "correctly excluded: 1" in out

    def test_json_mode(self, tmp_path, capsys):
        _repo(tmp_path, "landmine-repo", commands={
            "cleanup.md": "run git clean -fd now\n",
        })
        rc = sweep_mod.main(["--root", str(tmp_path), "--json"])
        parsed = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert parsed["finding_count"] == 1
        assert parsed["hits"][0]["token"] == "git clean -fd"

    def test_exit_2_on_bad_root(self, tmp_path, capsys):
        rc = sweep_mod.main(["--root", str(tmp_path / "missing")])
        assert rc == 2
        assert "not a directory" in capsys.readouterr().err


class TestWrappedGuardSentences:
    """The real fleet's only first-run false positive: a prohibition
    sentence wrapped across two lines, judged by its continuation alone."""

    def test_continuation_of_a_prohibition_is_a_guard(self, tmp_path):
        _repo(tmp_path, "wrapped", skills={
            "rista.md": (
                "Do NOT escalate to `--admin` /\n"
                "`--no-verify` / force-push / `branch -D`.\n"
            ),
        })
        hits = sweep_mod.sweep(tmp_path)
        assert hits, "tokens must still be detected"
        assert all(h["class"] == "guard" for h in hits)

    def test_instruction_with_unrelated_preceding_guard_still_flags(self, tmp_path):
        _repo(tmp_path, "tricky", commands={
            "x.md": (
                "Never commit secrets.\n"
                "\n"
                "Then run: git push --force origin main\n"
            ),
        })
        findings = [h for h in sweep_mod.sweep(tmp_path) if h["class"] == "instructor"]
        assert [h["token"] for h in findings] == ["force push"]
