"""The fleet's one model switch: a role names its model, and a dead model stops the run (#4450)."""

from __future__ import annotations

import pytest

from assemblyzero import fleet_models
from assemblyzero.fleet_models import ModelSwitchError, model_for, models_for, problems

TABLE = """
[roles]
judge = "fast"
second-eye = "old"
speech = ["fast", "other"]
banned = "argon"
nowhere = "missing"

[models.fast]
provider = "agy"
id = "gemini-3.8-flash-high"
status = "live"

[models.other]
provider = "gemini-api"
id = "gemini-3.8-flash-tts"
status = "live"

[models.old]
provider = "codex"
id = "gpt-6.1-sol"
status = "retired"

[models.argon]
provider = "agy"
id = "gemini-4-argon-high"
status = "live"

[policy]
forbidden = ["gemini-4-argon"]
"""


@pytest.fixture
def table(tmp_path):
    path = tmp_path / "fleet-models.toml"
    path.write_text(TABLE, encoding="utf-8")
    return path


def test_t1_changing_one_word_changes_the_model_a_role_gets(table):
    assert model_for("judge", table).id == "gemini-3.8-flash-high"
    table.write_text(TABLE.replace('judge = "fast"', 'judge = "other"'), encoding="utf-8")

    model = model_for("judge", table)

    assert (model.provider, model.id) == ("gemini-api", "gemini-3.8-flash-tts")


def test_t1_going_back_is_two_words(table):
    table.write_text(TABLE.replace('status = "retired"', 'status = "live"'), encoding="utf-8")

    model = model_for("second-eye", table)

    assert (model.provider, model.id) == ("codex", "gpt-6.1-sol")


def test_t2_a_retired_model_stops_the_run_through_except_exception(table):
    with pytest.raises(ModelSwitchError) as stopped:
        try:
            model_for("second-eye", table)
        except Exception:  # noqa: BLE001 - the tool's own handler, which must not swallow it
            pytest.fail("except Exception caught the stop")

    assert "second-eye" in str(stopped.value)
    assert "gpt-6.1-sol" in str(stopped.value)
    assert str(stopped.value).startswith("STOPPED:")


def test_t3_an_unknown_role_stops_the_run(table):
    with pytest.raises(ModelSwitchError, match="no role 'nobody'"):
        model_for("nobody", table)


def test_t3_a_missing_file_stops_the_run(tmp_path):
    with pytest.raises(ModelSwitchError, match="cannot be read"):
        model_for("judge", tmp_path / "absent.toml")


def test_t3_a_broken_file_stops_the_run(tmp_path):
    broken = tmp_path / "fleet-models.toml"
    broken.write_text("[roles\n", encoding="utf-8")

    with pytest.raises(ModelSwitchError, match="not valid TOML"):
        model_for("judge", broken)


def test_t3_a_forbidden_model_stops_the_run_even_when_marked_live(table):
    with pytest.raises(ModelSwitchError, match="forbidden by 'gemini-4-argon'"):
        model_for("banned", table)


def test_t3_a_role_naming_no_defined_model_stops_the_run(table):
    with pytest.raises(ModelSwitchError, match="not under"):
        model_for("nowhere", table)


def test_a_role_with_several_models_is_read_with_models_for(table):
    assert [m.name for m in models_for("speech", table)] == ["fast", "other"]

    with pytest.raises(ModelSwitchError, match="models_for"):
        model_for("speech", table)


def test_t4_the_check_names_every_role_with_no_live_model(table):
    found = problems(table)

    assert len(found) == 3
    assert any("second-eye" in line for line in found)
    assert any("banned" in line for line in found)
    assert any("nowhere" in line for line in found)


def test_t4_check_exits_1_and_prints_the_role(table, monkeypatch, capsys):
    monkeypatch.setattr(fleet_models, "FILE", table)

    assert fleet_models.main(["--check"]) == 1
    assert "NO LIVE MODEL: role 'second-eye'" in capsys.readouterr().out


def test_t4_check_exits_0_when_every_role_has_a_live_model(tmp_path, monkeypatch):
    clean = tmp_path / "fleet-models.toml"
    clean.write_text('[roles]\njudge = "fast"\n[models.fast]\nprovider = "agy"\nid = "x"\nstatus = "live"\n',
                     encoding="utf-8")
    monkeypatch.setattr(fleet_models, "FILE", clean)

    assert fleet_models.main(["--check"]) == 0


def test_t5_the_reviewer_constant_and_the_default_profile_read_the_switch():
    from assemblyzero.core import config, seats
    from assemblyzero.core.llm_provider import GeminiProvider

    assert config.REVIEWER_MODEL == model_for("reviewer").id
    assert config.FORBIDDEN_MODELS == list(fleet_models.forbidden())
    assert GeminiProvider.MODEL_MAP["3.1-pro"] == model_for("workflow").id
    spec = seats.load_profile(seats.builtin_path("gemini"))["defaults"]["spec"]
    assert GeminiProvider.MODEL_MAP[spec.split(":", 1)[1]] == model_for("workflow").id


def test_t6_the_real_file_defines_every_model_each_role_names():
    table = fleet_models.load()
    for role in table["roles"]:
        for name in fleet_models.names_of(table, role):
            assert name in table["models"], f"{role} names {name}"
    for name, entry in table["models"].items():
        assert entry["provider"] in fleet_models.PROVIDERS, name
        assert entry["status"] in fleet_models.STATUSES, name
        assert entry["id"], name


def test_t6_the_real_file_says_how_to_go_back_to_codex():
    text = fleet_models.FILE.read_text(encoding="utf-8")

    assert 'second-eye = "codex-sol"' in text
    assert 'status = "live"' in text
    assert "To go back to Codex" in text
