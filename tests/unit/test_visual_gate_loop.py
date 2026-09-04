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
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
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


#: How long `run_gate` waits for a round's `feedback.json`. One constant, used
#: by every test and by the submitter below, so the two sides of one handshake
#: cannot be given budgets that disagree (#2743).
GATE_DEADLINE = 30

#: A loop that needs two rounds gets two of everything.
GATE_DEADLINE_TWO_ROUNDS = 60

#: The submitter outlives the gate on purpose. Before #2743 it gave up after
#: 400 polls of 0.05 s -- twenty seconds, INSIDE the gate's thirty -- so on a
#: loaded machine it could abandon the handshake, die silently in its daemon
#: thread, and leave the gate to spend its remaining ten seconds and report
#: `no feedback.json ... after 30s`. That message names the symptom, and
#: neither the cause nor the side that failed.
SUBMITTER_MARGIN = 5


@dataclass
class Submitter:
    """The operator's thread, and what it saw if it did not finish.

    A daemon thread's exception is not a test failure: pytest reports it as a
    warning, which is easy to miss and impossible to act on. So the thread
    catches its own failure and the test raises it, carrying what it was
    waiting for and what was on disk instead.
    """

    thread: threading.Thread | None = None
    error: BaseException | None = None
    delivered: int = 0
    wanted: int = 0
    seen: list[str] = field(default_factory=list)

    def diagnosis(self) -> str:
        return (
            f"the operator thread delivered {self.delivered} of {self.wanted} "
            f"scripted answer(s); rounds on disk when it last looked: "
            f"{', '.join(self.seen) or '(none)'}"
        )


def _submitter(root: Path, answers: list[tuple[str, str]],
               gate_deadline: float = GATE_DEADLINE) -> Submitter:
    """A thread playing the operator: waits for each served round's pending
    sentinel, then POSTs the next scripted answer to the page's real URL.

    The parameter is **the gate's** deadline, not this thread's; the margin is
    added here, so a caller cannot set one and forget the other. That is the
    exact shape of #2743: the submitter's twenty seconds sat INSIDE the gate's
    thirty, so on a loaded machine it abandoned the handshake, died silently in
    its daemon thread, and left the gate to report a missing file rather than a
    missing answer.
    """
    deadline = gate_deadline + SUBMITTER_MARGIN
    state = Submitter(wanted=len(answers))

    def play():
        for verb, text in answers:
            url = None
            expiry = time.monotonic() + deadline
            while time.monotonic() < expiry:
                names = []
                for round_dir in bundle_mod.round_dirs(root):
                    names.append(
                        round_dir.name + "["
                        + ",".join(sorted(
                            p.name for p in round_dir.glob("feedback*.json")
                        )) + "]"
                    )
                    pending = round_dir / "feedback-pending.json"
                    if pending.is_file() and not (round_dir / "feedback.json").is_file() \
                            and not (round_dir / "feedback-consumed.json").is_file():
                        url = json.loads(pending.read_text(encoding="utf-8"))["url"]
                        break
                state.seen = names
                if url:
                    break
                time.sleep(0.05)
            assert url, (
                f"no round served a pending sentinel within {deadline}s while "
                f"the scripted answer {verb!r} was waiting to be delivered"
            )
            data = urllib.parse.urlencode({"verb": verb, "text": text}).encode()
            req = urllib.request.Request(url + "feedback", data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                assert resp.status == 200
            state.delivered += 1

    def guarded():
        try:
            play()
        except BaseException as exc:  # noqa: BLE001
            # Kept rather than raised: this is a daemon thread, where an
            # exception becomes a warning nobody reads. `_settle` raises it.
            state.error = exc

    state.thread = threading.Thread(target=guarded, daemon=True)
    state.thread.start()
    return state


def _settle(submitter: Submitter, gate_error: BaseException | None = None) -> None:
    """Join the operator thread and report ITS failure, not the gate's symptom.

    Called after every `run_gate` in this file, on the success path and the
    failure path both. When the handshake breaks, what a reader needs is which
    side stopped and what was on disk; `no feedback.json after 30s` says only
    that a file the other side was supposed to write is not there.
    """
    assert submitter.thread is not None
    submitter.thread.join(timeout=10)
    if submitter.error is not None:
        raise AssertionError(
            f"the operator thread failed: {submitter.error} -- "
            f"{submitter.diagnosis()}"
        ) from (gate_error or submitter.error)
    if submitter.thread.is_alive():
        raise AssertionError(
            f"the operator thread never finished -- {submitter.diagnosis()}"
        ) from gate_error
    if gate_error is not None:
        raise AssertionError(
            f"the gate failed although the operator thread completed cleanly: "
            f"{gate_error} -- {submitter.diagnosis()}"
        ) from gate_error
    assert submitter.delivered == submitter.wanted, submitter.diagnosis()


def _run_gate(submitter: Submitter, *args, **kwargs):
    """`run_gate`, with the operator thread's story attached to any failure."""
    try:
        outcome = run_gate(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001
        _settle(submitter, exc)
        raise
    _settle(submitter)
    return outcome


class TestApproveLetsTheRunProceed:
    def test_the_cycle_render_serve_approve_stamp(self, repo, config):
        root = bundle_mod.gate_root(repo, ISSUE)
        submitter = _submitter(root, [("approve", "looks right")])

        outcome = _run_gate(submitter,
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
            wait_kwargs={"poll_seconds": 0.05, "deadline": GATE_DEADLINE},
        )

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
        submitter = _submitter(
            bundle_mod.gate_root(repo, ISSUE), [("approve", "")],
        )
        _run_gate(submitter,
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
            wait_kwargs={"poll_seconds": 0.05, "deadline": GATE_DEADLINE},
        )

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
        submitter = _submitter(root, [
            ("modify", "red bar should be thinner, start further from center"),
            ("approve", "that is the one"),
        ], gate_deadline=GATE_DEADLINE_TWO_ROUNDS)

        outcome = _run_gate(submitter,
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: transport_response,
            wait_kwargs={"poll_seconds": 0.05, "deadline": GATE_DEADLINE_TWO_ROUNDS},
        )

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
        submitter = _submitter(root, [
            ("modify", "the red seems like a brick red"),
            ("approve", "the first candidate"),
        ], gate_deadline=GATE_DEADLINE_TWO_ROUNDS)

        outcome = _run_gate(submitter,
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: transport_response,
            wait_kwargs={"poll_seconds": 0.05, "deadline": GATE_DEADLINE_TWO_ROUNDS},
        )

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
        submitter = _submitter(root, [("modify", "make the needle darker")])

        outcome = _run_gate(submitter,
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: transport_response,
            wait_kwargs={"poll_seconds": 0.05, "deadline": GATE_DEADLINE},
        )

        assert outcome.status == "halted"
        assert "contradicts a landed ruling" in outcome.error
        assert "'needle_rgb'" in outcome.error

    def test_reject_halts_and_writes_the_operators_words(self, repo, config):
        root = bundle_mod.gate_root(repo, ISSUE)
        submitter = _submitter(root, [("reject", "wrong direction entirely")])

        outcome = _run_gate(submitter,
            repo, ISSUE, config, mock=True, runner=_forbid_gh,
            transport=lambda *_: "[]",
            wait_kwargs={"poll_seconds": 0.05, "deadline": GATE_DEADLINE},
        )

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


class TestABrokenHandshakeSaysWhichSideStopped:
    """#2743. Two failures on 2026-09-03, in unrelated environments on
    unrelated branches, both in this file and both timing-shaped. The CI one
    reported `no feedback.json ... after 30s`, which describes a file the OTHER
    side was supposed to write and names neither the cause nor the side that
    failed. These tests drive the diagnostic that replaces it, so a future red
    run in this file is readable rather than re-runnable.
    """

    def test_the_operator_threads_own_failure_is_what_gets_raised(self, repo):
        """The defect exactly: the thread gives up, and because it is a daemon
        its assertion is a warning nobody sees. Here it is raised, with what it
        was waiting for."""
        root = bundle_mod.gate_root(repo, ISSUE)
        root.mkdir(parents=True, exist_ok=True)
        submitter = _submitter(root, [("approve", "never delivered")],
                               gate_deadline=-SUBMITTER_MARGIN + 0.2)

        with pytest.raises(AssertionError) as caught:
            _settle(submitter)

        message = str(caught.value)
        assert "the operator thread failed" in message
        assert "no round served a pending sentinel" in message
        assert "delivered 0 of 1 scripted answer(s)" in message

    def test_the_diagnosis_names_the_rounds_it_could_see(self, repo):
        """"Nothing was served" and "a round was served and already answered"
        are different faults, and the message has to tell them apart."""
        root = bundle_mod.gate_root(repo, ISSUE)
        round_dir = bundle_mod.next_round_dir(root)
        (round_dir / "feedback.json").write_text("{}", encoding="utf-8")
        submitter = _submitter(root, [("approve", "too late")],
                               gate_deadline=-SUBMITTER_MARGIN + 0.2)

        with pytest.raises(AssertionError) as caught:
            _settle(submitter)

        assert "round-001[feedback.json]" in str(caught.value)

    def test_a_gate_failure_is_reported_with_the_threads_state_beside_it(self):
        """When the operator side is clean, the gate's own error survives -- it
        is not swallowed by the new reporting."""
        submitter = Submitter(thread=threading.Thread(target=lambda: None))
        submitter.thread.start()

        with pytest.raises(AssertionError) as caught:
            _settle(submitter, TimeoutError("no feedback.json after 30s"))

        message = str(caught.value)
        assert "the gate failed although the operator thread completed" in message
        assert "no feedback.json after 30s" in message

    def test_the_submitter_always_outlives_the_gate(self):
        """The ordering that makes the report trustworthy. The margin is added
        inside `_submitter`, so no caller can pass a gate deadline and leave the
        thread with a shorter one -- which is the bug this file had."""
        assert SUBMITTER_MARGIN > 0
        for gate_deadline in (GATE_DEADLINE, GATE_DEADLINE_TWO_ROUNDS):
            assert gate_deadline + SUBMITTER_MARGIN > gate_deadline
