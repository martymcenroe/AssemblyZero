"""N3 validate_completeness under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md, at ``79e18ad1``. A check that
cannot run raises ``CompletenessCannotCheck``; N3 turns it into one halt
(``completeness_cannot_check`` and ``error_message``), which the router sends
to HALT and HALT alerts. A defect in the draft fails its check, which the
drafter can revise. Absence that is a legitimate answer stays quiet and is
pinned here.
"""
from __future__ import annotations

import importlib
import inspect
import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.graph import route_after_validation

# `nodes/__init__` re-exports the FUNCTION under the module's name.
vc = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
)
rp = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.revision_pinning"
)
CannotCheck = vc.CompletenessCannotCheck

LLD = (
    "# LLD\n\n## 10. Test Plan\n\n"
    "| ID | Scenario | Pass Criteria |\n"
    "|----|----------|---------------|\n"
    "| 010 | adding one (REQ-1) | returns 2 |\n"
)
SPEC = "# Spec\n\n" + "This spec says what changes, and where, in plain words.\n" * 4


def _fence(body: str, tag: str = "python") -> str:
    return f"```{tag}\n{body}\n```\n"


def _repo(tmp_path: Path, *, package: bool = True) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    if package:
        (repo / "boostgauge").mkdir()
        (repo / "boostgauge" / "__init__.py").write_text("", encoding="utf-8")
    return repo


def _node_state(tmp_path: Path, **kw) -> dict:
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        "spec_draft": SPEC,
        "files_to_modify": [],
        "pattern_references": [],
        "repo_root": str(_repo(tmp_path)),
        "lld_content": LLD,
        "gathered_symbols": [],
        "review_iteration": 0,
        "max_iterations": 3,
        "issue_number": 42,
        "audit_dir": str(audit),
        "assemblyzero_root": str(tmp_path),
    }
    state.update(kw)
    return state


def _halted(out: dict, capsys) -> str:
    """The node halted through its one cannot-check return."""
    message = out["completeness_cannot_check"]
    assert out["error_message"] == message
    assert message.startswith("N3 completeness gate cannot run:")
    assert out["validation_passed"] is False
    assert "ERROR [N3]" in capsys.readouterr().err
    assert route_after_validation({**out, "review_iteration": 0, "max_iterations": 3}) == "HALT"
    return message


def _fake_run(monkeypatch, *, poetry=None, probe=None, git=None) -> None:
    """Answer poetry, the env probe and git ls-tree; anything else runs."""
    real = subprocess.run

    def answer(spec, args):
        if isinstance(spec, BaseException):
            raise spec
        code, out, err = spec
        return subprocess.CompletedProcess(args, code, out, err)

    def run(args, *a, **kw):
        argv = list(args)
        if argv[:3] == ["poetry", "env", "info"] and poetry is not None:
            return answer(poetry, argv)
        if argv[:2] == ["git", "ls-tree"] and git is not None:
            return answer(git, argv)
        if len(argv) > 1 and argv[1] == "-c" and probe is not None:
            return answer(probe, argv)
        return real(args, *a, **kw)

    monkeypatch.setattr(vc.subprocess, "run", run)


def _refuse_for(monkeypatch, method: str, target: Path) -> None:
    real = getattr(Path, method)

    def refused(self, *a, **kw):
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, method, refused)


# ---------------------------------------------------------------------------
# The node
# ---------------------------------------------------------------------------


class TestTheNode:
    def test_132_an_empty_draft_at_the_cap_halts_with_a_reason(self):
        out = vc.validate_completeness({
            "spec_draft": "", "review_iteration": 3, "max_iterations": 3,
        })
        assert out["validation_passed"] is False
        assert out["error_message"].startswith("Iteration cap:")
        assert "empty or too short" in out["error_message"]
        assert route_after_validation({**out, "review_iteration": 3, "max_iterations": 3}) == "HALT"

    def test_an_empty_draft_below_the_cap_still_revises(self):
        """Kept: a short draft is a draft defect, revised below the cap."""
        out = vc.validate_completeness({
            "spec_draft": "short", "review_iteration": 0, "max_iterations": 3,
        })
        assert out["error_message"] == ""
        assert "empty or too short" in out["completeness_issues"][0]
        assert route_after_validation({**out, "review_iteration": 0, "max_iterations": 3}) == "N2_generate_spec"

    def test_280_telemetry_that_cannot_be_recorded_halts_n3(self, tmp_path, monkeypatch, capsys):
        def broken(*_a, **_kw):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(vc, "_record_hallucination_telemetry", broken)
        message = _halted(vc.validate_completeness(_node_state(tmp_path)), capsys)
        assert "telemetry" in message
        assert "OSError" in message and "No space left" in message

    def test_1455_n3_without_a_repo_root_halts(self, tmp_path, capsys):
        message = _halted(vc.validate_completeness(_node_state(tmp_path, repo_root="")), capsys)
        assert "repo root" in message

    def test_1879_n3_without_the_lld_halts(self, tmp_path, capsys):
        message = _halted(vc.validate_completeness(_node_state(tmp_path, lld_content="")), capsys)
        assert "LLD" in message

    def test_a_complete_state_reaches_a_verdict(self, tmp_path):
        """Kept: with what N3 needs, the checks run and give a verdict."""
        out = vc.validate_completeness(_node_state(tmp_path))
        assert out["error_message"] == ""
        assert "completeness_cannot_check" not in out


# ---------------------------------------------------------------------------
# Checks that cannot run without what N3 needs
# ---------------------------------------------------------------------------


class TestWhatN3Needs:
    def test_1342_pattern_refs_without_a_repo_root_cannot_check(self):
        refs = [{"file_path": "src/a.py", "start_line": 1, "end_line": 2}]
        with pytest.raises(CannotCheck, match="repo root"):
            vc.check_pattern_references_valid("# Spec\nsrc/a.py\n", refs, "")

    def test_no_pattern_refs_is_not_applicable(self):
        """Kept: N1 finding no pattern references is an answer."""
        check = vc.check_pattern_references_valid("# Spec\n", [], "")
        assert check["passed"] and "not applicable" in check["details"]

    def test_1455_the_import_check_without_a_repo_root_cannot_check(self):
        with pytest.raises(CannotCheck, match="repo root"):
            vc.check_import_targets_exist(_fence("import boostgauge.gauge"), [], "")

    def test_1702_the_call_check_without_a_repo_root_cannot_check(self):
        with pytest.raises(CannotCheck, match="repo root"):
            vc.check_call_signatures_match(_fence("x = 1"), [], "")

    def test_1879_criteria_without_the_lld_cannot_check(self):
        with pytest.raises(CannotCheck, match="LLD"):
            vc.check_criteria_have_tests(_fence("def test_x():\n    assert 1"), "")

    def test_1892_an_lld_with_no_criteria_table_cannot_check(self):
        with pytest.raises(CannotCheck, match="pass-criteria table"):
            vc.check_criteria_have_tests(SPEC, "# LLD\n\nNo tables here.\n")

    def test_1892_untagged_criteria_cannot_check(self):
        untagged = (
            "# LLD\n\n| ID | Scenario | Pass Criteria |\n|---|---|---|\n"
            "| 010 | adding one | returns 2 |\n"
        )
        with pytest.raises(CannotCheck, match="REQ tag"):
            vc.check_criteria_have_tests(SPEC, untagged)

    def test_tagged_criteria_still_gate(self):
        """Kept: a tagged table is a join, and a miss fails the check."""
        missing = vc.check_criteria_have_tests(SPEC, LLD)
        assert not missing["passed"] and "REQ-1" in missing["details"]
        covered = vc.check_criteria_have_tests(
            _fence('def test_add():\n    """REQ-1"""\n    assert 1 + 1 == 2'), LLD
        )
        assert covered["passed"]


# ---------------------------------------------------------------------------
# The target environment
# ---------------------------------------------------------------------------


class TestTheTargetEnvironment:
    def test_1530_third_party_imports_with_no_env_answer_cannot_check(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        _fake_run(monkeypatch, poetry=(1, "", "Poetry could not find a pyproject.toml"))
        with pytest.raises(CannotCheck) as raised:
            vc.check_import_targets_exist(_fence("import requests.adapters"), [], str(repo))
        assert str(repo) in str(raised.value)
        assert "exited 1" in str(raised.value)
        assert "could not find a pyproject" in str(raised.value)

    def test_3873_unbound_roots_with_no_env_answer_cannot_check(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        _fake_run(monkeypatch, poetry=(1, "", "no virtualenv"))
        spec = _fence("def collect():\n    psutil.Process(1)")
        with pytest.raises(CannotCheck, match="no virtualenv"):
            vc.check_api_symbols_exist(spec, ["collect"], str(repo))

    def test_4380_poetry_that_cannot_run_cannot_check(self, tmp_path, monkeypatch):
        _fake_run(monkeypatch, poetry=FileNotFoundError(2, "No such file or directory", "poetry"))
        with pytest.raises(CannotCheck, match="FileNotFoundError"):
            vc._target_env_python(tmp_path)

    def test_4380_poetry_that_times_out_cannot_check(self, tmp_path, monkeypatch):
        _fake_run(monkeypatch, poetry=subprocess.TimeoutExpired(["poetry"], 30))
        with pytest.raises(CannotCheck, match="TimeoutExpired"):
            vc._target_env_python(tmp_path)

    def test_4382_poetry_that_exits_nonzero_names_its_code_and_stderr(self, tmp_path, monkeypatch):
        _fake_run(monkeypatch, poetry=(1, "", "No virtualenv has been activated"))
        with pytest.raises(CannotCheck) as raised:
            vc._target_env_python(tmp_path)
        assert "exited 1" in str(raised.value)
        assert "No virtualenv has been activated" in str(raised.value)

    def test_4382_an_env_that_holds_no_python_cannot_check(self, tmp_path, monkeypatch):
        venv = tmp_path / "venv"
        venv.mkdir()
        _fake_run(monkeypatch, poetry=(0, f"{venv}\n", ""))
        with pytest.raises(CannotCheck, match="no python"):
            vc._target_env_python(tmp_path)

    def test_4417_a_probe_that_exits_nonzero_names_its_code_and_stderr(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vc, "_target_env_python", lambda _repo: "/env/bin/python")
        _fake_run(monkeypatch, probe=(1, "", "Traceback: boom"))
        with pytest.raises(CannotCheck) as raised:
            vc._probe_target_env(tmp_path, ["requests"])
        assert "exited 1" in str(raised.value) and "boom" in str(raised.value)

    def test_4417_a_probe_that_prints_nothing_cannot_check(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vc, "_target_env_python", lambda _repo: "/env/bin/python")
        _fake_run(monkeypatch, probe=(0, "", ""))
        with pytest.raises(CannotCheck, match="no output"):
            vc._probe_target_env(tmp_path, ["requests"])

    @pytest.mark.parametrize("answer, cause", [
        (subprocess.TimeoutExpired(["python"], 60), "TimeoutExpired"),
        ((0, "not json\n", ""), "not JSON"),
        ((0, "[1, 2]\n", ""), "not a JSON object"),
    ])
    def test_4423_a_probe_that_times_out_or_prints_bad_json_cannot_check(
        self, tmp_path, monkeypatch, answer, cause,
    ):
        monkeypatch.setattr(vc, "_target_env_python", lambda _repo: "/env/bin/python")
        _fake_run(monkeypatch, probe=answer)
        with pytest.raises(CannotCheck, match=cause):
            vc._probe_target_env(tmp_path, ["requests"])

    def test_a_probe_that_answers_is_read(self, tmp_path, monkeypatch):
        """Kept: a real answer is the answer."""
        monkeypatch.setattr(vc, "_target_env_python", lambda _repo: "/env/bin/python")
        _fake_run(monkeypatch, probe=(0, '{"requests": true, "nope": false}\n', ""))
        assert vc._probe_target_env(tmp_path, ["requests", "nope"]) == {
            "requests": True, "nope": False,
        }


# ---------------------------------------------------------------------------
# The repo's own packages and pyproject
# ---------------------------------------------------------------------------


class TestTheRepoLayout:
    def test_1614_a_failed_git_listing_names_the_ref_and_stderr(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        _fake_run(monkeypatch, git=(128, "", "fatal: Not a valid object name origin/nope"))
        with pytest.raises(CannotCheck) as raised:
            vc._same_named_modules("boostgauge.renderer", repo, "origin/nope")
        assert "origin/nope" in str(raised.value)
        assert "fatal: Not a valid object name" in str(raised.value)

    def test_3890_a_repo_that_cannot_be_listed_cannot_check(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        _refuse_for(monkeypatch, "iterdir", repo)
        with pytest.raises(CannotCheck, match="PermissionError"):
            vc._first_party_tops_for(str(repo))

    def test_no_repo_root_owns_no_packages(self):
        """Kept: a caller that names no repo (the telemetry of a standalone
        detector call) treats every import as foreign, by its docstring."""
        assert vc._first_party_tops_for("") == frozenset()

    def test_4355_a_src_dir_that_cannot_be_listed_cannot_check(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path, package=False)
        (repo / "src" / "boostgauge").mkdir(parents=True)
        _refuse_for(monkeypatch, "iterdir", repo / "src")
        with pytest.raises(CannotCheck, match="src"):
            vc._first_party_tops(repo)

    def test_4360_a_pyproject_read_failure_is_not_swallowed(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text('[project]\nname = "boostgauge"\n', encoding="utf-8")
        _refuse_for(monkeypatch, "read_text", repo / "pyproject.toml")
        with pytest.raises(CannotCheck, match="PermissionError"):
            vc._first_party_tops(repo)

    def test_4167_an_unparseable_pyproject_cannot_name_source_roots(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text("this = = not toml\n", encoding="utf-8")
        with pytest.raises(CannotCheck) as raised:
            vc._discover_pyproject_source_roots(repo)
        assert str(repo / "pyproject.toml") in str(raised.value)

    def test_4288_an_unparseable_pyproject_cannot_name_the_package(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text("this = = not toml\n", encoding="utf-8")
        with pytest.raises(CannotCheck) as raised:
            vc._pyproject_declared_package(repo)
        assert str(repo / "pyproject.toml") in str(raised.value)

    def test_a_repo_with_no_pyproject_declares_nothing(self, tmp_path):
        """Kept: no pyproject is an answer, not a failure."""
        repo = _repo(tmp_path)
        assert vc._discover_pyproject_source_roots(repo) == ()
        assert vc._pyproject_declared_package(repo) == set()
        assert vc._first_party_tops(repo) == {"boostgauge"}


# ---------------------------------------------------------------------------
# The fixture check's pyproject
# ---------------------------------------------------------------------------

SECTION_TEN_MOCKER = (
    "# Spec\n\n## 10. Test Mapping\n\n"
    + _fence("def test_a(mocker):\n    assert mocker is not None")
)


class TestTheFixtureCheck:
    def test_1988_an_invalid_pyproject_cannot_check(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text("this = = not toml\n", encoding="utf-8")
        with pytest.raises(CannotCheck) as raised:
            vc.check_spec_test_fixtures_resolvable(SECTION_TEN_MOCKER, str(repo), "")
        assert "not valid TOML" in str(raised.value)
        assert str(repo) in str(raised.value)

    def test_2036_an_unreadable_base_pyproject_cannot_check(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        monkeypatch.setattr(vc, "base_ref", lambda _root, _branch: "origin/arc")

        def unreadable(*_a):
            raise OSError(2, "No such file or directory", "git")

        monkeypatch.setattr(vc, "read_from_base", unreadable)
        with pytest.raises(CannotCheck) as raised:
            vc._pyproject_for_run(str(repo), "arc")
        # OSError(2, ...) is constructed as its errno subclass.
        assert "'arc'" in str(raised.value) and "FileNotFoundError" in str(raised.value)

    def test_2050_an_unreadable_checkout_pyproject_cannot_check(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").mkdir()
        with pytest.raises(CannotCheck, match="IsADirectoryError"):
            vc._pyproject_for_run(str(repo), "")

    def test_a_repo_with_no_pyproject_declares_no_plugins(self, tmp_path):
        """Kept: a missing pyproject declares nothing, and the report says where
        it looked."""
        text, source = vc._pyproject_for_run(str(_repo(tmp_path)), "")
        assert text == ""
        assert "pyproject" in source

    def test_2037_2051_1988_no_fail_open_tag_remains(self):
        for function in (vc._pyproject_for_run, vc._declared_dependencies):
            assert "fail-open" not in inspect.getsource(function)


# ---------------------------------------------------------------------------
# Section 10
# ---------------------------------------------------------------------------


class TestSectionTen:
    def test_2083_a_function_the_draft_does_not_hold_cannot_check(self):
        functions = [{"name": "test_x", "source": "def test_x():\n    assert 1"}]
        with pytest.raises(CannotCheck, match="test_x"):
            vc._test_function_spans("# Spec\n", functions)

    def test_2194_a_spec_with_no_section_ten_fails_the_check(self):
        check = vc.check_section_ten_carries_test_functions("# Spec\n\n## 6. Changes\n\nText.\n")
        assert check["passed"] is False
        assert "Section 10" in check["details"]
        assert rp.demands_additions([check["details"]])

    def test_2222_an_extractor_refusal_is_named_in_the_failure(self):
        spec = (
            "# Spec\n\n## 9. Test Mapping\n\nOld mapping.\n\n## 10. Test Mapping\n\n"
            + _fence("def test_a():\n    assert True")
        )
        check = vc.check_section_ten_carries_test_functions(spec)
        assert check["passed"] is False
        assert "Legacy Section 9" in check["details"]

    def test_2223_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(vc.check_section_ten_carries_test_functions)

    def test_2419_an_unparseable_section_ten_block_fails_the_fixture_check(self):
        spec = "# Spec\n\n## 10. Test Mapping\n\n" + _fence("def test_a(tmp_path):\n    assert (")
        check = vc.check_spec_test_fixtures_resolvable(spec, "", "")
        assert check["passed"] is False
        assert "SyntaxError" in check["details"]
        assert "lines" in check["details"]

    def test_2420_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(vc.check_spec_test_fixtures_resolvable)


# ---------------------------------------------------------------------------
# Manifest traceability and the symbol check
# ---------------------------------------------------------------------------

TRACED_TEST = _fence("def test_s11():\n    # manifest: S1.1\n    assert True")


class TestManifestTraceability:
    def test_2641_an_unparseable_python_fence_fails_the_check(self):
        spec = TRACED_TEST + "\n" + _fence("def broken(:")
        check = vc.check_manifest_traceability(spec, [{"row_id": "S1.1"}])
        assert check["passed"] is False
        assert "SyntaxError" in check["details"]
        assert "lines" in check["details"]

    def test_an_unparseable_untagged_fence_is_counted_not_failed(self):
        """Kept: an untagged fence claimed no Python (the 3535 contract)."""
        spec = TRACED_TEST + "\n" + _fence("def broken(:", tag="")
        check = vc.check_manifest_traceability(spec, [{"row_id": "S1.1"}])
        assert check["passed"] is True
        assert "not judged" in check["details"]

    def test_2641_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(vc.check_manifest_traceability)


class TestTheSymbolCheck:
    BASE = (
        "import ctypes\n\nclass Thing(ctypes.NoSuchBase):\n"
        "    def go(self):\n        self.frobnicate_now()"
    )

    def test_3439_an_unresolvable_stdlib_base_is_named_at_error(self, capsys):
        check = vc.check_api_symbols_exist(_fence(self.BASE), ["unrelated"], "")
        assert "ctypes.NoSuchBase" in check["details"]
        err = capsys.readouterr().err
        assert "ERROR [N3]" in err and "ctypes.NoSuchBase" in err

    def test_3439_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(vc._resolve_stdlib_class)

    def test_a_resolvable_stdlib_base_still_lends_its_methods(self, capsys):
        """Kept (#2839): an inherited method is the base's to be right about."""
        spec = _fence(
            "import ast\n\nclass V(ast.NodeVisitor):\n"
            "    def go(self, tree):\n        self.generic_visit(tree)"
        )
        check = vc.check_api_symbols_exist(spec, ["unrelated"], "")
        assert check["passed"]
        assert "ERROR" not in capsys.readouterr().err

    WIN = _fence("def apply(win):\n    win.model_dump()")

    def test_3932_no_symbols_in_a_python_repo_cannot_judge_its_calls(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        monkeypatch.setattr(vc, "_probe_target_env", lambda _r, tops: {t: False for t in tops})
        with pytest.raises(CannotCheck, match="gathered no symbols"):
            vc.check_api_symbols_exist(self.WIN, [], str(repo))

    def test_3932_no_symbols_in_a_repo_with_no_packages_still_judges(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path, package=False)
        monkeypatch.setattr(vc, "_probe_target_env", lambda _r, tops: {t: False for t in tops})
        check = vc.check_api_symbols_exist(self.WIN, [], str(repo))
        assert check["passed"] is False
        assert "model_dump" in check["details"]

    def test_3932_no_symbols_and_nothing_to_judge_passes_on_evidence(self, tmp_path):
        spec = _fence("items = []\nitems.append(1)")
        check = vc.check_api_symbols_exist(spec, [], str(_repo(tmp_path)))
        assert check["passed"] is True
        assert "skipped" not in check["details"]

    def test_3932_no_symbols_still_reports_python_that_does_not_parse(self):
        check = vc.check_api_symbols_exist(_fence("def broken(:"), [], "")
        assert check["check_name"] == "python_fences_parse"
        assert check["passed"] is False


# ---------------------------------------------------------------------------
# The two rows #3767 fixed, pinned
# ---------------------------------------------------------------------------


def _broken_callee_repo(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)
    (repo / "boostgauge" / "telltale.py").write_text("def broken(:\n", encoding="utf-8")
    return repo


class TestTheRowsFixedBy3767:
    def test_1725_an_unparseable_fence_is_left_to_python_fences_parse(self, tmp_path):
        spec = _fence("def broken(:")
        assert vc.check_call_signatures_match(spec, [], str(_repo(tmp_path)))["passed"]
        assert vc.check_api_symbols_exist(spec, ["x"], "")["check_name"] == "python_fences_parse"

    def test_1746_a_callee_that_does_not_parse_cannot_check(self, tmp_path):
        spec = _fence("from boostgauge.telltale import Telltale\nTelltale(window=1)")
        with pytest.raises(CannotCheck, match="boostgauge.telltale"):
            vc.check_call_signatures_match(spec, [], str(_broken_callee_repo(tmp_path)))
