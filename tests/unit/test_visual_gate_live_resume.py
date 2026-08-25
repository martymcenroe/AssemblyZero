"""The first live hour's defects, pinned (#2521, #2520).

The acceptance scenario is real: boostgauge round-001's preserved
feedback.json carries verb modify and the operator's words verbatim --
"extend the need to the exact radius of the start of the minor tick mark" --
translated tip 0.86 R -> 0.95 R, which radially re-enters the band (inner
0.88 R) and amends the 2026-08-25 tip-short-of-band restatement. These tests
build that exact shape: an OLD manifest that predates needle_tip, the
declaration's ruled pin, and the words unchanged.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from assemblyzero.visual_gate import bundle as bundle_mod
from assemblyzero.visual_gate import modify as modify_mod
from assemblyzero.visual_gate.config import GateConfig
from assemblyzero.visual_gate.gate import _with_declared_ruled, run_gate
from assemblyzero.visual_gate.server import pending_url, wait_for_feedback

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll  # noqa: E402

ISSUE = 331

#: The operator's preserved words, verbatim per the issue's requirement.
OPERATOR_WORDS = (
    "extend the need to the exact radius of the start of the minor tick mark"
)

#: The round-001 manifest shape: rendered BEFORE needle_tip joined the
#: contract, so the key is absent -- the live resume's exact starting state.
STALE_MANIFEST = {
    "values": {
        "band_inner": {"value": 0.88,
                       "source": "operator ruling 2026-08-25", "ruled": True},
        "band_rgb": {"value": [170, 15, 25],
                     "source": "operator ruling 2026-08-25", "ruled": True},
        "needle_rgb": {"value": [247, 57, 35],
                       "source": "ruling #228", "ruled": True},
        "wordmark_y": {"value": 0.67,
                       "source": "operator ruling 2026-08-25", "ruled": True},
    },
    "palette": {"needle": [247, 57, 35], "band": [170, 15, 25],
                "white": [255, 255, 255], "face": [10, 10, 12]},
}

TRANSLATION = json.dumps([{
    "kind": "modify-geometry", "key": "needle_tip", "value": 0.95,
    "note": "extend the needle tip to 0.95 R, the minor tick start -- this "
            "re-enters the band (inner 0.88 R) and amends the tip-short-of-"
            "band restatement",
}])

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x00\x03\x00\x01\x9d\xc0\x0e\xf5\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def repo(tmp_path) -> Path:
    """A target repo holding the live shape: round-001 with images, the stale
    manifest, and the operator's UNCONSUMED feedback."""
    r = tmp_path / "boostgauge"
    round_dir = r / "data" / "visual-gate" / str(ISSUE) / "round-001"
    round_dir.mkdir(parents=True)
    (round_dir / "face-1024.png").write_bytes(PNG_1PX)
    (round_dir / "manifest.json").write_text(
        json.dumps(STALE_MANIFEST), encoding="utf-8",
    )
    (round_dir / "overrides.json").write_text("{}", encoding="utf-8")
    (round_dir / "feedback-pending.json").write_text(
        '{"served_at": "2026-08-25T22:30:00+00:00", '
        '"url": "http://127.0.0.1:56772/"}',
        encoding="utf-8",
    )
    bundle_mod.write_feedback(round_dir, "modify", OPERATOR_WORDS)
    return r


@pytest.fixture
def config() -> GateConfig:
    return GateConfig(
        issues=(ISSUE,),
        renderer_cmd=("python", "tools/never_invoked_here.py"),
        contract="docs/design/0002-aesthetic-v1-stingray.md",
        separation_floor=85.0,
        ruled={
            "needle_rgb": [247, 57, 35], "band_rgb": [170, 15, 25],
            "band_inner": 0.88, "wordmark_y": 0.67, "needle_tip": 0.86,
        },
    )


class TestResumeHonoursSubmittedFeedback:
    """#2521 requirement 1: a submitted verdict is state, not a prompt to
    repeat -- the resume consumes it and never re-serves the round."""

    def test_the_preserved_modify_dispatches_without_reserving(
        self, repo, config
    ):
        pending_before = (
            repo / "data" / "visual-gate" / str(ISSUE) / "round-001"
            / "feedback-pending.json"
        ).read_text(encoding="utf-8")

        outcome = run_gate(
            repo, ISSUE, config, mock=True,
            transport=lambda *_: TRANSLATION,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 2},
        )

        # It dispatched (reaching the ruling surface below) rather than
        # timing out waiting on a click the operator already gave.
        assert outcome.status == "halted"
        assert "landed ruling" in outcome.error
        pending_after = (
            repo / "data" / "visual-gate" / str(ISSUE) / "round-001"
            / "feedback-pending.json"
        ).read_text(encoding="utf-8")
        assert pending_after == pending_before, (
            "re-serving would rewrite the pending sentinel -- it must not"
        )


class TestTheLiveFeedbackReachesTheRulingSurface:
    """#2521's acceptance scenario, words verbatim: the tip delta amends the
    tip-short-of-band restatement and is SURFACED, never silently applied."""

    def test_the_verbatim_words_travel_to_the_model_pass(self, repo, config):
        captured = {}

        def transport(system, content):
            captured["content"] = content
            return TRANSLATION

        run_gate(
            repo, ISSUE, config, mock=True, transport=transport,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 2},
        )

        assert OPERATOR_WORDS in captured["content"]

    def test_the_stale_manifest_still_offers_the_ruled_key(self, repo, config):
        """The declaration's ruled values are contract vocabulary even when
        the round predates them -- without this the ask files as a vague
        contract gap instead of reaching the ruling surface."""
        captured = {}

        def transport(system, content):
            captured["content"] = content
            return TRANSLATION

        run_gate(
            repo, ISSUE, config, mock=True, transport=transport,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 2},
        )

        assert "needle_tip" in captured["content"]
        assert "[RULED" in captured["content"]

    def test_the_delta_halts_with_the_interaction_stated(self, repo, config):
        outcome = run_gate(
            repo, ISSUE, config, mock=True,
            transport=lambda *_: TRANSLATION,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 2},
        )

        assert outcome.status == "halted"
        assert "contradicts a landed ruling" in outcome.error
        assert "'needle_tip'" in outcome.error
        assert "0.86" in outcome.error and "0.95" in outcome.error
        assert "re-enters the band" in outcome.error, (
            "the interaction is stated, not just the key"
        )

    def test_merging_declared_ruled_keys_never_clobbers_the_manifest(self):
        merged = _with_declared_ruled(
            STALE_MANIFEST, {"needle_tip": 0.86, "band_inner": 0.99},
        )

        assert merged["values"]["needle_tip"]["value"] == 0.86
        assert merged["values"]["needle_tip"]["ruled"] is True
        assert merged["values"]["band_inner"]["value"] == 0.88, (
            "a key the manifest carries keeps the manifest's own record"
        )
        assert "needle_tip" not in STALE_MANIFEST["values"], (
            "the merge returns a copy; the round's manifest is history"
        )


class TestAModelPassFailureHaltsResumably:
    """#2521 requirement 2: an infra error is not a verdict -- the stage
    halts resumably with the feedback preserved, and the resumed stage
    consumes it. The first live Modify let this kill the whole run."""

    def test_the_crash_becomes_a_halt_and_the_feedback_survives(
        self, repo, config
    ):
        def broken_transport(*_):
            raise RuntimeError(
                "Model 'claude-opus-4-6' is not a valid Gemini model"
            )

        outcome = run_gate(
            repo, ISSUE, config, mock=True, transport=broken_transport,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 2},
        )

        assert outcome.status == "halted"
        assert "not an operator verdict" in outcome.error
        assert "preserved unconsumed" in outcome.error
        round_dir = repo / "data" / "visual-gate" / str(ISSUE) / "round-001"
        assert (round_dir / "feedback.json").is_file(), (
            "the operator's submitted verdict survives the infra error"
        )
        assert not (round_dir / "feedback-consumed.json").exists()

    def test_the_resume_after_the_crash_dispatches_the_same_feedback(
        self, repo, config
    ):
        """The full live cycle: crash on the broken transport, resume with a
        working one, the SAME preserved feedback reaches the ruling surface
        without the operator clicking again."""
        run_gate(
            repo, ISSUE, config, mock=True,
            transport=lambda *_: (_ for _ in ()).throw(RuntimeError("wiring")),
            wait_kwargs={"poll_seconds": 0.05, "deadline": 2},
        )

        outcome = run_gate(
            repo, ISSUE, config, mock=True,
            transport=lambda *_: TRANSLATION,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 2},
        )

        assert outcome.status == "halted"
        assert "contradicts a landed ruling" in outcome.error


class TestTheTransportWiring:
    """#2521 requirement 3: the translation call routes through the provider
    layer, which pairs model id with transport."""

    def test_default_transport_uses_the_provider_layer(self, monkeypatch):
        calls = {}

        class _Result:
            success = True
            response = TRANSLATION
            error_message = ""

        def fake_get_provider(spec, effort=None):
            calls["spec"] = spec

            class _P:
                def invoke(self, system, content, **_kw):
                    calls["system"] = system
                    return _Result()

            return _P()

        import assemblyzero.core.llm_provider as llm_provider
        monkeypatch.setattr(llm_provider, "get_provider", fake_get_provider)

        out = modify_mod.default_transport("sys prompt", "content")

        assert calls["spec"] == modify_mod.TRANSLATION_PROVIDER
        assert calls["spec"].startswith("gemini:"), (
            "the spec routes a Gemini model to the Gemini transport"
        )
        assert out == TRANSLATION

    def test_a_provider_failure_raises_naming_the_spec(self, monkeypatch):
        class _Result:
            success = False
            response = None
            error_message = "quota exhausted"

        import assemblyzero.core.llm_provider as llm_provider
        monkeypatch.setattr(
            llm_provider, "get_provider",
            lambda spec, effort=None: type(
                "P", (), {"invoke": lambda self, s, c, **_kw: _Result()}
            )(),
        )

        with pytest.raises(RuntimeError) as err:
            modify_mod.default_transport("s", "c")

        assert modify_mod.TRANSLATION_PROVIDER in str(err.value)
        assert "quota exhausted" in str(err.value)


class TestTheWaitingLineSaysTheURL:
    """#2520: every repeat of the waiting line is actionable on sight."""

    def test_the_reminder_prints_the_url_from_the_sentinel(self, tmp_path):
        round_dir = tmp_path / "round-001"
        round_dir.mkdir()
        (round_dir / "feedback-pending.json").write_text(
            '{"url": "http://127.0.0.1:56772/"}', encoding="utf-8",
        )
        lines = []

        with pytest.raises(TimeoutError):
            wait_for_feedback(
                round_dir, poll_seconds=0.02, reminder_every=0.01,
                deadline=0.2, log=lines.append,
            )

        assert lines, "at least one reminder fired in the window"
        assert all("open http://127.0.0.1:56772/" in line for line in lines)
        assert all("round-001" in line for line in lines)

    def test_a_missing_or_broken_sentinel_never_breaks_the_wait(self, tmp_path):
        round_dir = tmp_path / "round-001"
        round_dir.mkdir()
        assert pending_url(round_dir) == ""
        (round_dir / "feedback-pending.json").write_text("{not json",
                                                         encoding="utf-8")
        assert pending_url(round_dir) == ""


class TestTheLauncherAnnouncesTheURL:
    """#2520: the launcher's own surface (detached-launcher.log is its
    stdout) says the URL once per served round."""

    def _run_watch(self, repo_root, announce, cycles=0.4):
        stop = threading.Event()
        thread = threading.Thread(
            target=speedrun_roll._watch_visual_gate_urls,
            args=(repo_root, stop),
            kwargs={"announce": announce, "poll_seconds": 0.05},
            daemon=True,
        )
        thread.start()
        time.sleep(cycles)
        stop.set()
        thread.join(timeout=5)

    def test_a_served_round_is_announced_once_with_the_url(self, tmp_path):
        round_dir = tmp_path / "data" / "visual-gate" / "331" / "round-001"
        round_dir.mkdir(parents=True)
        (round_dir / "feedback-pending.json").write_text(
            '{"url": "http://127.0.0.1:56772/"}', encoding="utf-8",
        )
        announced = []

        self._run_watch(tmp_path, lambda line, **_kw: announced.append(line))

        assert len(announced) == 1, "once per round, not once per poll"
        assert "http://127.0.0.1:56772/" in announced[0]
        assert "331" in announced[0] and "round-001" in announced[0]

    def test_an_answered_round_is_not_announced(self, tmp_path):
        round_dir = tmp_path / "data" / "visual-gate" / "331" / "round-001"
        round_dir.mkdir(parents=True)
        (round_dir / "feedback-pending.json").write_text(
            '{"url": "http://127.0.0.1:56772/"}', encoding="utf-8",
        )
        (round_dir / "feedback.json").write_text(
            '{"verb": "modify", "text": "words"}', encoding="utf-8",
        )
        announced = []

        self._run_watch(tmp_path, lambda line, **_kw: announced.append(line))

        assert announced == []

    def test_a_repo_with_no_gate_is_silent_and_harmless(self, tmp_path):
        announced = []
        self._run_watch(tmp_path, lambda line, **_kw: announced.append(line))
        assert announced == []
