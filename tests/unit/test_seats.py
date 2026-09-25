"""Seats and model profiles (#3563, under umbrella #3562).

T1 the loader, T2 the precedence, T3 the built-in profiles, and the code-path
walk (the umbrella's T1) that keeps every model choice in a profile. The walk
parses source with ``ast``; it never matches text with a regular expression.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from assemblyzero.core import seats
from assemblyzero.core.seats import (
    SEATS,
    ProfileError,
    apply_overrides,
    builtin_path,
    builtin_profiles,
    legacy_keys,
    load_profile,
    load_run_profile,
    parse_profile,
    profile_of,
    resolve,
    seat_in,
    seat_table,
    select_profile_path,
)

REPO = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


GEMINI_ONLY = 'name = "x"\n[defaults]\nspec = "gemini:3.1-pro"\neffort = "max"\n'


# ---------------------------------------------------------------------------
# T1: the loader
# ---------------------------------------------------------------------------


class TestTheLoader:
    def test_the_registry_is_the_seventeen_seats(self):
        assert len(SEATS) == 17
        assert list(SEATS)[0] == "requirements.analyze"
        assert "impl.code.small" in SEATS and "impl.adversarial" in SEATS

    def test_a_valid_file_round_trips(self, tmp_path):
        path = _write(
            tmp_path / "p.toml",
            GEMINI_ONLY + '[seats."impl.code"]\nspec = "claude:sonnet"\neffort = "low"\n',
        )
        profile = load_profile(path)
        assert profile["name"] == "x"
        assert profile["defaults"] == {"spec": "gemini:3.1-pro", "effort": "max"}
        assert profile["seats"] == {"impl.code": {"spec": "claude:sonnet", "effort": "low"}}
        assert len(profile["sha256"]) == 64
        assert seat_in(profile, "impl.code").spec == "claude:sonnet"
        assert seat_in(profile, "impl.code").effort == "low"
        assert seat_in(profile, "impl.code.small").spec == "gemini:3.1-pro"

    def test_an_unknown_seat_fails_closed_naming_it(self, tmp_path):
        path = _write(tmp_path / "p.toml", GEMINI_ONLY + '[seats."impl.coder"]\nspec = "gemini:3.1-pro"\n')
        with pytest.raises(ProfileError, match="impl.coder"):
            load_profile(path)

    def test_a_forbidden_model_fails_closed_naming_seat_and_model(self, tmp_path):
        path = _write(tmp_path / "p.toml", GEMINI_ONLY + '[seats."spec.review"]\nspec = "gemini:2.5-flash"\n')
        with pytest.raises(ProfileError) as err:
            load_profile(path)
        assert "spec.review" in str(err.value) and "gemini-2.5-flash" in str(err.value)

    def test_a_forbidden_model_under_any_provider_fails_closed(self):
        with pytest.raises(ProfileError, match="gemini-2.5-flash"):
            apply_overrides(seats.default_profile(), {"impl.code": "mock:gemini-2.5-flash"})

    def test_a_spec_with_no_colon_fails_under_parse_provider_spec(self, tmp_path):
        path = _write(tmp_path / "p.toml", GEMINI_ONLY + '[seats."impl.code"]\nspec = "sonnet"\n')
        with pytest.raises(ProfileError, match="provider:model"):
            load_profile(path)

    def test_an_unknown_provider_is_left_to_get_provider(self):
        """Requirement 2 fences what parses and what is forbidden; which
        providers exist is get_provider's to say, when the seat is used."""
        from assemblyzero.core.llm_provider import get_provider

        profile = apply_overrides(seats.default_profile(), {"impl.code": "bogus:spec"})
        seat = seat_in(profile, "impl.code")
        assert (seat.spec, seat.resolved_model_id) == ("bogus:spec", "spec")
        with pytest.raises(ValueError, match="Unknown provider 'bogus'"):
            get_provider(seat.spec)

    def test_a_forbidden_gemini_alias_is_caught_in_its_full_form(self):
        with pytest.raises(ProfileError, match="gemini-3-pro"):
            apply_overrides(seats.default_profile(), {"spec.review": "gemini:3-pro"})

    def test_no_defaults_and_a_missing_seat_fails_closed(self):
        with pytest.raises(ProfileError, match="no \\[defaults\\] spec"):
            parse_profile('name = "x"\n[seats."impl.code"]\nspec = "gemini:3.1-pro"\n', "t")

    def test_an_unknown_top_level_key_fails_closed(self):
        with pytest.raises(ProfileError, match="unknown top-level"):
            # Before any table header, so TOML puts the key at the top level.
            parse_profile('drafter = "claude:opus"\n' + GEMINI_ONLY, "t")

    def test_an_effort_override_reaches_every_seat(self):
        profile = apply_overrides(load_profile(builtin_path("claude")), effort="high")
        assert {seat.effort for seat in seat_table(profile).values()} == {"high"}


# ---------------------------------------------------------------------------
# T2: precedence, and the snapshot on resume
# ---------------------------------------------------------------------------


class TestPrecedence:
    @pytest.fixture
    def everything(self, tmp_path, monkeypatch):
        """All four levels present at once, each naming a different profile."""
        target = tmp_path / "target"
        _write(target / ".assemblyzero" / "models.toml", 'name = "from-target"\n[defaults]\nspec = "gemini:3.1-pro"\n')
        env_file = _write(tmp_path / "env.toml", 'name = "from-env"\n[defaults]\nspec = "gemini:3.1-pro"\n')
        flag_file = _write(tmp_path / "flag.toml", 'name = "from-flag"\n[defaults]\nspec = "gemini:3.1-pro"\n')
        monkeypatch.setenv("AZ_MODEL_PROFILE", str(env_file))
        return target, flag_file

    def test_the_flag_wins_over_everything(self, everything):
        target, flag_file = everything
        assert load_run_profile(str(flag_file), target)["name"] == "from-flag"

    def test_the_environment_wins_over_the_target_and_builtin(self, everything):
        target, _ = everything
        profile = load_run_profile(None, target)
        assert (profile["name"], profile["selected_by"]) == ("from-env", "env")

    def test_the_target_wins_over_the_builtin(self, everything, monkeypatch):
        target, _ = everything
        monkeypatch.delenv("AZ_MODEL_PROFILE")
        profile = load_run_profile(None, target)
        assert (profile["name"], profile["selected_by"]) == ("from-target", "target")

    def test_the_builtin_gemini_is_the_floor(self, tmp_path):
        how, path = select_profile_path(None, tmp_path, environ={})
        assert (how, path.name) == ("builtin", "gemini.toml")
        assert load_run_profile(None, tmp_path)["name"] == "gemini"

    def test_a_name_resolves_against_the_builtin_directory(self, tmp_path):
        assert load_run_profile("claude", tmp_path)["name"] == "claude"

    def test_an_unknown_name_fails_closed_listing_the_builtins(self, tmp_path):
        with pytest.raises(ProfileError, match="gemini"):
            load_run_profile("nonesuch", tmp_path)

    def test_mock_wins_over_every_source(self, everything):
        target, flag_file = everything
        assert load_run_profile(str(flag_file), target, mock=True)["name"] == "mock"

    def test_a_resumed_run_reads_the_snapshot_not_the_file(self, tmp_path):
        path = _write(tmp_path / "p.toml", GEMINI_ONLY)
        state = {"model_profile": load_run_profile(str(path), tmp_path)}
        _write(path, 'name = "x"\n[defaults]\nspec = "claude:opus"\n')
        assert resolve(state, "impl.code").spec == "gemini:3.1-pro"


# ---------------------------------------------------------------------------
# T3: the built-in profiles
# ---------------------------------------------------------------------------

CLAUDE_TABLE = {
    "requirements.analyze": "claude:sonnet",
    "requirements.analyze.escalation": "claude:opus",
    "requirements.draft": "claude:sonnet",
    "requirements.review": "claude:opus",
    "requirements.contract_fidelity": "gemini:3.1-pro",
    "spec.draft": "claude:opus",
    "spec.review": "claude:opus",
    "impl.test_plan.review": "claude:opus",
    "impl.test_plan.revise": "claude:opus",
    "impl.code": "claude:sonnet",
    "impl.code.small": "claude:haiku",
    "impl.augment_tests": "claude:sonnet",
    "impl.adversarial": "gemini:3.1-pro",
    "orchestrator.triage_summary": "claude:haiku",
    "visual_gate.translate": "gemini:3.1-pro",
    "scout.analyze": "gemini:3.1-pro",
    "tools.audit_deferred_scope": "claude:opus",
}


class TestTheBuiltInProfiles:
    def test_the_three_exist(self):
        assert {"gemini", "claude", "mock"} <= set(builtin_profiles())

    def test_gemini_puts_every_seat_on_gemini_at_max(self):
        for name, seat in seat_table(load_profile(builtin_path("gemini"))).items():
            assert (seat.spec, seat.effort) == ("gemini:3.1-pro", "max"), name
            assert seat.resolved_model_id == "gemini-3.1-pro-high", name
            assert seat.provider == "GeminiProvider", name

    def test_claude_reproduces_the_pre_law_table(self):
        table = seat_table(load_profile(builtin_path("claude")))
        assert {name: seat.spec for name, seat in table.items()} == CLAUDE_TABLE
        assert table["impl.augment_tests"].effort == "low"
        assert table["impl.code.small"].resolved_model_id == "claude-haiku-4-5"

    def test_mock_puts_every_seat_on_the_mock_provider(self):
        table = seat_table(load_profile(builtin_path("mock")))
        assert {seat.provider for seat in table.values()} == {"MockProvider"}
        assert table["requirements.draft"].spec == "mock:lld"
        assert table["requirements.review"].spec == "mock:review"
        assert table["spec.draft"].spec == "mock:draft"

    def test_the_legacy_keys_come_from_the_profile(self):
        keys = legacy_keys(load_profile(builtin_path("claude")))
        assert keys == {
            "config_drafter": "claude:sonnet",
            "config_reviewer": "claude:opus",
            "config_effort": "max",
        }


# ---------------------------------------------------------------------------
# The entry points: --mock, --seat, and the old flags (T4, T5)
# ---------------------------------------------------------------------------


class TestTheEntryPoints:
    def test_mock_selects_the_mock_profile_on_the_implementation_tool(self, tmp_path):
        from assemblyzero.core.seats import profile_from_args
        from tools.run_implement_from_lld import create_argument_parser

        args = create_argument_parser().parse_args(["--issue", "42", "--mock"])
        profile = profile_from_args(args, tmp_path)

        assert profile["name"] == "mock"
        assert {s.provider for s in seat_table(profile).values()} == {"MockProvider"}

    def test_mock_drops_a_real_override_by_name(self, tmp_path, capsys):
        from assemblyzero.core.seats import profile_from_args
        from tools.run_implement_from_lld import create_argument_parser

        args = create_argument_parser().parse_args(
            ["--issue", "42", "--mock", "--seat", "impl.code=claude:sonnet",
             "--seat", "impl.code.small=mock:small"]
        )
        profile = profile_from_args(args, tmp_path)

        assert seat_in(profile, "impl.code").spec == "mock:mock"
        assert seat_in(profile, "impl.code.small").spec == "mock:small"
        assert "ignoring impl.code=claude:sonnet" in capsys.readouterr().out

    def test_the_issue_workflow_mock_drafts_the_issue_response(self, tmp_path):
        from tools.run_requirements_workflow import parse_args, run_profile_for

        args = parse_args(["--type", "issue", "--brief", "b.md", "--mock"])
        assert seat_in(run_profile_for(args, tmp_path), "requirements.draft").spec == "mock:draft"

    def test_a_drafter_override_leaves_every_other_seat(self, tmp_path):
        """T5: --drafter claude:opus moves requirements.draft and nothing else
        beyond the drafter seats the flag always reached."""
        from tools.run_requirements_workflow import parse_args, run_profile_for

        args = parse_args(["--type", "lld", "--issue", "42", "--drafter", "claude:opus"])
        table = seat_table(run_profile_for(args, tmp_path))

        moved = {n for n, s in table.items() if s.spec != "gemini:3.1-pro"}
        assert moved == {
            "requirements.analyze", "requirements.draft", "requirements.analyze.escalation",
        }
        assert table["requirements.draft"].spec == "claude:opus"

    def test_seat_wins_over_the_old_flag(self, tmp_path):
        from tools.run_requirements_workflow import parse_args, run_profile_for

        args = parse_args([
            "--type", "lld", "--issue", "42", "--drafter", "claude:opus",
            "--seat", "requirements.draft=claude:sonnet",
        ])
        profile = run_profile_for(args, tmp_path)
        assert seat_in(profile, "requirements.draft").spec == "claude:sonnet"
        assert seat_in(profile, "requirements.analyze").spec == "claude:opus"

    def test_models_names_a_builtin(self, tmp_path):
        from assemblyzero.core.seats import profile_from_args
        from tools.run_implementation_spec_workflow import parse_args

        args = parse_args(["--issue", "42", "--models", "claude"])
        assert seat_in(profile_from_args(args, tmp_path), "spec.draft").spec == "claude:opus"


# ---------------------------------------------------------------------------
# Hand-built state: one release of compatibility, in one place
# ---------------------------------------------------------------------------


class TestHandBuiltState:
    def test_no_profile_and_no_keys_is_the_default(self):
        assert resolve({}, "impl.code").spec == "gemini:3.1-pro"

    def test_the_legacy_drafter_reaches_the_drafter_seats(self):
        state = {"config_drafter": "claude:sonnet", "config_reviewer": "claude:opus"}
        assert resolve(state, "requirements.draft").spec == "claude:sonnet"
        assert resolve(state, "requirements.analyze.escalation").spec == "claude:opus"
        assert resolve(state, "spec.review").spec == "claude:opus"
        assert resolve(state, "impl.code").spec == "gemini:3.1-pro"

    def test_mock_state_keeps_the_old_mock_choices(self):
        assert resolve({"config_mock_mode": True}, "requirements.draft").spec == "mock:lld"
        issue = {"config_mock_mode": True, "workflow_type": "issue"}
        assert resolve(issue, "requirements.draft").spec == "mock:draft"
        named = {"config_mock_mode": True, "config_drafter": "mock:draft"}
        assert resolve(named, "requirements.draft").spec == "mock:draft"
        real = {"config_mock_mode": True, "config_drafter": "gemini:3.1-pro"}
        assert resolve(real, "requirements.draft").spec == "mock:lld"

    def test_a_snapshot_wins_over_the_legacy_keys(self):
        state = {
            "model_profile": load_profile(builtin_path("gemini")),
            "config_drafter": "claude:sonnet",
        }
        assert profile_of(state)["name"] == "gemini"
        assert resolve(state, "requirements.draft").spec == "gemini:3.1-pro"


# ---------------------------------------------------------------------------
# The umbrella's T1 and #3563 requirement 5: every model choice is a seat
# ---------------------------------------------------------------------------

PREFIXES = ("claude:", "gemini:", "anthropic:", "codex:")
LEGACY_KEYS = frozenset({"config_drafter", "config_reviewer", "config_effort"})
WALKED = ("assemblyzero", "tools")
EXEMPT = frozenset({"assemblyzero/core/seats.py"})


def _string_head(node: ast.AST) -> str | None:
    """The literal text a node starts with, for a str constant or an f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and node.values:
        first = node.values[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _is_spec_literal(node: ast.AST) -> bool:
    head = _string_head(node)
    return head is not None and head.strip().lower().startswith(PREFIXES)


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def findings(root: Path = REPO) -> list[str]:
    """Every place a model is chosen outside the registry, as ``rel:line: what``."""
    out: list[str] = []
    for top in WALKED:
        for path in sorted((root / top).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if rel in EXEMPT or "/done/" in rel:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=rel)
            for node in tree.body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                    if _is_spec_literal(node.value):
                        out.append(f"{rel}:{node.lineno}: module constant is a provider spec")
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = _call_name(node)
                    if name == "get_provider" and node.args and _is_spec_literal(node.args[0]):
                        out.append(f"{rel}:{node.lineno}: get_provider with a literal spec")
                    if (
                        name == "get"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value in LEGACY_KEYS
                    ):
                        out.append(f"{rel}:{node.lineno}: reads {node.args[0].value}")
                elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
                    key = node.slice
                    if isinstance(key, ast.Constant) and key.value in LEGACY_KEYS:
                        out.append(f"{rel}:{node.lineno}: reads {key.value}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for default in node.args.defaults + node.args.kw_defaults:
                        if default is not None and _is_spec_literal(default):
                            out.append(f"{rel}:{node.lineno}: parameter default is a provider spec")
    return out


class TestEveryModelChoiceIsASeat:
    def test_the_tree_has_none_outside_the_registry(self):
        hits = findings()
        assert hits == [], "\n".join(hits)

    def test_the_walk_sees_each_kind(self, tmp_path):
        _write(tmp_path / "tools" / "__init__.py", "")
        _write(
            tmp_path / "assemblyzero" / "bad.py",
            'SPEC = "claude:opus"\n'
            "def f(state, spec='gemini:3.1-pro'):\n"
            "    get_provider(f\"claude:{state}\")\n"
            '    return state.get("config_drafter", "") or state["config_effort"]\n',
        )
        kinds = [hit.split(": ", 1)[1] for hit in findings(tmp_path)]
        assert sorted(kinds) == sorted([
            "module constant is a provider spec",
            "parameter default is a provider spec",
            "get_provider with a literal spec",
            "reads config_drafter",
            "reads config_effort",
        ])
