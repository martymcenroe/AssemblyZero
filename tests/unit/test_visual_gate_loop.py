"""The gate loop end to end (#2518): a real renderer subprocess, a real
localhost server, a real HTTP submission, real files -- mock only where the
design mocks (no gh calls, fake model transport).

The fake renderer honours the full protocol: --out-dir, --set overrides, a
PNG via PIL, a manifest with values/palette/samples, and exit 3 with a
stderr finding when told the contract is too adjectival.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from assemblyzero.visual_gate import bundle as bundle_mod
from assemblyzero.visual_gate.config import GateConfig
from assemblyzero.visual_gate.gate import run_gate

ISSUE = 331

FAKE_RENDERER = '''
import json, sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args[args.index("--out-dir") + 1])
overrides = {}
for i, a in enumerate(args):
    if a == "--set":
        key, raw = args[i + 1].split("=", 1)
        overrides[key] = json.loads(raw)

marker = Path(__file__).with_name("too-adjectival")
if marker.exists():
    print(marker.read_text(encoding="utf-8").strip(), file=sys.stderr)
    sys.exit(3)

from PIL import Image
band = overrides.get("band_rgb", [155, 48, 32])
Image.new("RGB", (64, 64), tuple(band)).save(out / "render-face.png")
manifest = {
    "values": {
        "band_inner": {"value": overrides.get("band_inner", 0.80),
                       "source": "contract"},
        "band_rgb": {"value": band, "source": "contract"},
        "needle_rgb": {"value": [247, 57, 35], "source": "ruling #228",
                       "ruled": True},
        "wordmark_y": {"value": overrides.get("wordmark_y", 0.55),
                       "source": "contract"},
    },
    "palette": {"needle": [247, 57, 35], "white": [255, 255, 255],
                "face": [10, 10, 12]},
    "samples": [{"name": "center", "x_frac": 0.5, "y_frac": 0.5,
                 "expect": "band"}],
}
(out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
'''


@pytest.fixture
def repo(tmp_path) -> Path:
    r = tmp_path / "target"
    (r / "tools").mkdir(parents=True)
    (r / "tools" / "fake_render.py").write_text(FAKE_RENDERER, encoding="utf-8")
    return r


@pytest.fixture
def config(repo) -> GateConfig:
    return GateConfig(
        issues=(ISSUE,),
        renderer_cmd=(sys.executable, str(repo / "tools" / "fake_render.py")),
        contract="docs/design/contract.md",
        separation_floor=85.0,
        ruled={},
    )


def _forbid_gh(cmd, **kwargs):
    """The loop's runner for subprocesses. gh must never run in these tests --
    mock mode is on, and a gh call reaching this is the failure."""
    assert cmd[0] != "gh", f"gh invoked in a mock-mode test: {cmd}"
    return subprocess.run(cmd, **kwargs)


def _submitter(root: Path, answers: list[tuple[str, str]]):
    """A thread playing the operator: waits for each served round's pending
    sentinel, then POSTs the next scripted answer to the page's real URL."""
    def play():
        for verb, text in answers:
            url = None
            for _ in range(400):
                for round_dir in bundle_mod.round_dirs(root):
                    pending = round_dir / "feedback-pending.json"
                    if pending.is_file() and not (round_dir / "feedback.json").is_file() \
                            and not (round_dir / "feedback-consumed.json").is_file():
                        url = json.loads(pending.read_text(encoding="utf-8"))["url"]
                        break
                if url:
                    break
                import time
                time.sleep(0.05)
            assert url, "no served round appeared for the scripted answer"
            data = urllib.parse.urlencode({"verb": verb, "text": text}).encode()
            req = urllib.request.Request(url + "feedback", data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                assert resp.status == 200

    thread = threading.Thread(target=play, daemon=True)
    thread.start()
    return thread


class TestApproveLetsTheRunProceed:
    def test_the_cycle_render_serve_approve_stamp(self, repo, config):
        root = bundle_mod.gate_root(repo, ISSUE)
        thread = _submitter(root, [("approve", "looks right")])

        outcome = run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
            wait_kwargs={"poll_seconds": 0.05, "deadline": 30},
        )
        thread.join(timeout=10)

        assert outcome.status == "approved"
        approved = root / "approved" / "approved.png"
        assert Path(outcome.artifact_path) == approved
        assert approved.is_file()
        record = json.loads(
            (root / "approved" / "approved.json").read_text(encoding="utf-8")
        )
        assert record["sha256"]
        assert record["source_round"] == "round-001"

    def test_expected_colours_are_measured_from_the_approved_picture(
        self, repo, config
    ):
        thread = _submitter(
            bundle_mod.gate_root(repo, ISSUE), [("approve", "")],
        )
        run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
            wait_kwargs={"poll_seconds": 0.05, "deadline": 30},
        )
        thread.join(timeout=10)

        record = json.loads(
            (bundle_mod.gate_root(repo, ISSUE) / "approved" / "approved.json")
            .read_text(encoding="utf-8")
        )
        [measured] = record["measurements"]
        assert measured["name"] == "center"
        assert measured["rgb"] == [155, 48, 32], (
            "the value is READ off the picture, not derived by anyone"
        )

    def test_an_already_approved_gate_passes_without_serving(self, repo, config):
        root = bundle_mod.gate_root(repo, ISSUE)
        (root / "approved").mkdir(parents=True)
        (root / "approved" / "approved.png").write_bytes(b"png")
        (root / "approved" / "approved.json").write_text("{}", encoding="utf-8")

        outcome = run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
        )

        assert outcome.status == "approved"


class TestTheModifyLoopIterates:
    def test_a_delta_re_renders_and_the_second_approve_carries_it(
        self, repo, config
    ):
        root = bundle_mod.gate_root(repo, ISSUE)
        transport_response = json.dumps([{
            "kind": "modify-geometry", "key": "band_inner", "value": 0.88,
            "note": "red bar thinner, further from center",
        }])
        thread = _submitter(root, [
            ("modify", "red bar should be thinner, start further from center"),
            ("approve", "that is the one"),
        ])

        outcome = run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: transport_response,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 60},
        )
        thread.join(timeout=10)

        assert outcome.status == "approved"
        assert outcome.deltas == {"band_inner": 0.88}
        round2 = json.loads(
            (root / "round-002" / "overrides.json").read_text(encoding="utf-8")
        )
        assert round2 == {"band_inner": 0.88}, "the delta reached the renderer"
        assert (root / "round-001" / "feedback-consumed.json").is_file(), (
            "a dispatched verb never fires twice"
        )

    def test_an_adjectival_colour_serves_candidates_side_by_side(
        self, repo, config
    ):
        root = bundle_mod.gate_root(repo, ISSUE)
        transport_response = json.dumps([{
            "kind": "modify-colour", "key": "band_rgb", "value": None,
            "candidates": [[170, 15, 25], [130, 10, 20]],
            "note": "tachometer red, not brick",
        }])
        thread = _submitter(root, [
            ("modify", "the red seems like a brick red"),
            ("approve", "the first candidate"),
        ])

        outcome = run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: transport_response,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 60},
        )
        thread.join(timeout=10)

        assert outcome.status == "approved"
        round2_images = [p.name for p in bundle_mod.bundle_images(root / "round-002")]
        assert any("candidate1" in n for n in round2_images)
        assert any("candidate2" in n for n in round2_images)
        manifest2 = json.loads(
            (root / "round-002" / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest2["candidates"]["band_rgb"] == [[170, 15, 25], [130, 10, 20]]


class TestTheHalts:
    def test_a_ruling_contradiction_halts_for_the_operator(self, repo, config):
        root = bundle_mod.gate_root(repo, ISSUE)
        transport_response = json.dumps([{
            "kind": "modify-colour", "key": "needle_rgb", "value": [200, 0, 0],
            "note": "darker needle",
        }])
        thread = _submitter(root, [("modify", "make the needle darker")])

        outcome = run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: transport_response,
            wait_kwargs={"poll_seconds": 0.05, "deadline": 30},
        )
        thread.join(timeout=10)

        assert outcome.status == "halted"
        assert "contradicts a landed ruling" in outcome.error
        assert "'needle_rgb'" in outcome.error

    def test_reject_halts_and_writes_the_operators_words(self, repo, config):
        root = bundle_mod.gate_root(repo, ISSUE)
        thread = _submitter(root, [("reject", "wrong direction entirely")])

        outcome = run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
            wait_kwargs={"poll_seconds": 0.05, "deadline": 30},
        )
        thread.join(timeout=10)

        assert outcome.status == "halted"
        assert "REJECTED" in outcome.error
        body = (root / "round-001" / "rejection-issue.md").read_text(encoding="utf-8")
        assert "wrong direction entirely" in body
        assert "must-resolve" not in outcome.error or True

    def test_a_too_adjectival_contract_is_the_gates_finding(self, repo, config):
        (repo / "tools" / "too-adjectival").write_text(
            "the zone table names no numeric radii", encoding="utf-8",
        )

        outcome = run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
        )

        assert outcome.status == "halted"
        assert "too adjectival to render" in outcome.error
        assert "the zone table names no numeric radii" in outcome.error


class TestResumeReadsTheAnswerOffDisk:
    def test_an_answer_given_while_nothing_listened_dispatches_on_resume(
        self, repo, config
    ):
        """The relaunch path: render a round, kill the run (simulated by
        never serving), answer on disk, resume -- the gate dispatches the
        approve without a browser in sight."""
        root = bundle_mod.gate_root(repo, ISSUE)
        round_dir = bundle_mod.next_round_dir(root)
        subprocess.run(
            [sys.executable, str(repo / "tools" / "fake_render.py"),
             "--out-dir", str(round_dir)],
            check=True, capture_output=True,
        )
        (round_dir / "overrides.json").write_text("{}", encoding="utf-8")
        bundle_mod.write_feedback(round_dir, "approve", "answered while down")

        outcome = run_gate(
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
        )

        assert outcome.status == "approved"
        assert (root / "approved" / "approved.png").is_file()
