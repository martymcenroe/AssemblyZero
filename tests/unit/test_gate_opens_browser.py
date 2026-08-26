"""The gate pulls the review page up itself (#2528).

"the url was clickable thank god but can't the program actually pull the url
up?" — each ROUND's first serve opens the operator's default browser, once; a
re-served round (a resume finding the pending sentinel already on disk) does
not re-open; a repo declaration or the environment turns it off; failure is
one logged line and never touches the wait. Real renderer subprocess, real
server, real files — the only fake is the browser itself.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

import pytest

from assemblyzero.visual_gate import bundle as bundle_mod
from assemblyzero.visual_gate.config import GateConfig, load_gate_config
from assemblyzero.visual_gate.gate import (
    OPEN_BROWSER_ENV,
    _open_review_page,
    run_gate,
)

ISSUE = 331

FAKE_RENDERER = '''
import json, sys
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("--out-dir") + 1])
from PIL import Image
Image.new("RGB", (8, 8), (155, 48, 32)).save(out / "render-face.png")
(out / "manifest.json").write_text(json.dumps({
    "values": {"band_inner": {"value": 0.80, "source": "contract"}},
    "palette": {"face": [10, 10, 12]},
}), encoding="utf-8")
'''


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(OPEN_BROWSER_ENV, raising=False)


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


@pytest.fixture
def opened(monkeypatch) -> list[str]:
    """A recording stand-in for the operator's browser."""
    calls: list[str] = []

    def fake_open(url: str) -> bool:
        calls.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)
    return calls


def _run(repo, config, deadline=3.0, mock=False):
    return run_gate(
        repo, ISSUE, config, mock=mock,
        transport=lambda *_: "[]",
        wait_kwargs={
            "poll_seconds": 0.05, "deadline": deadline,
            "notify_config": None,
        },
    )


class TestFirstServeOpens:
    def test_the_first_serve_opens_the_page_once(self, repo, config, opened):
        with pytest.raises(TimeoutError):
            _run(repo, config, deadline=1.0)
        assert len(opened) == 1
        rounds = bundle_mod.round_dirs(bundle_mod.gate_root(repo, ISSUE))
        pending = json.loads(
            (rounds[0] / "feedback-pending.json").read_text(encoding="utf-8")
        )
        assert opened[0] == pending["url"], (
            "the tab and the sentinel must name the same page"
        )

    def test_a_resumed_round_does_not_reopen(self, repo, config, opened):
        """The pending sentinel on disk is the fact 'the operator already got
        a tab for this picture' — a resume re-serves without re-opening."""
        with pytest.raises(TimeoutError):
            _run(repo, config, deadline=0.5)
        assert len(opened) == 1
        with pytest.raises(TimeoutError):
            _run(repo, config, deadline=0.5)  # the resume: same round, re-served
        assert len(opened) == 1, "the resume re-opened an already-seen round"

    def test_a_new_round_after_modify_opens_again(self, repo, config, opened):
        """A new picture is a new request for eyes."""
        root = bundle_mod.gate_root(repo, ISSUE)

        def submit_modify():
            for _ in range(200):
                for round_dir in bundle_mod.round_dirs(root):
                    pending = round_dir / "feedback-pending.json"
                    if pending.is_file() and not (
                        round_dir / "feedback-consumed.json"
                    ).is_file() and not (round_dir / "feedback.json").is_file():
                        url = json.loads(
                            pending.read_text(encoding="utf-8")
                        )["url"]
                        data = urllib.parse.urlencode(
                            {"verb": "modify", "text": "nudge the band"}
                        ).encode()
                        req = urllib.request.Request(
                            url + "feedback", data=data, method="POST"
                        )
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            assert resp.status == 200
                        return
                time.sleep(0.05)

        thread = threading.Thread(target=submit_modify, daemon=True)
        thread.start()
        with pytest.raises(TimeoutError):
            _run(repo, config, deadline=8.0)  # round-002 serves, nobody answers
        thread.join(timeout=10)
        assert len(opened) == 2, opened

    def test_mock_mode_never_opens(self, repo, config, opened):
        with pytest.raises(TimeoutError):
            _run(repo, config, deadline=0.5, mock=True)
        assert opened == []


class TestTheSwitches:
    def test_the_repo_declaration_turns_it_off(self, repo, config, opened):
        quiet = GateConfig(
            issues=config.issues, renderer_cmd=config.renderer_cmd,
            contract=config.contract, separation_floor=config.separation_floor,
            ruled={}, open_browser=False,
        )
        with pytest.raises(TimeoutError):
            _run(repo, quiet, deadline=0.5)
        assert opened == []

    def test_the_environment_turns_it_off(self, repo, config, opened, monkeypatch):
        monkeypatch.setenv(OPEN_BROWSER_ENV, "0")
        with pytest.raises(TimeoutError):
            _run(repo, config, deadline=0.5)
        assert opened == []

    def test_the_declaration_parses_from_json(self, tmp_path):
        gate_json = tmp_path / "docs" / "design" / "visual-gate.json"
        gate_json.parent.mkdir(parents=True)
        gate_json.write_text(json.dumps({
            "issues": [1], "renderer_cmd": ["x"], "contract": "c",
            "separation_floor": 1, "open_browser": False,
        }), encoding="utf-8")
        assert load_gate_config(tmp_path).open_browser is False

    def test_the_declaration_defaults_on(self, tmp_path):
        """Default ON is the operator's explicit request."""
        gate_json = tmp_path / "docs" / "design" / "visual-gate.json"
        gate_json.parent.mkdir(parents=True)
        gate_json.write_text(json.dumps({
            "issues": [1], "renderer_cmd": ["x"], "contract": "c",
            "separation_floor": 1,
        }), encoding="utf-8")
        assert load_gate_config(tmp_path).open_browser is True


class TestFailureIsNonFatal:
    def test_a_raising_browser_is_one_logged_line(self, config):
        lines: list[str] = []

        def broken(_url: str) -> bool:
            raise RuntimeError("no DISPLAY")

        _open_review_page(
            "http://127.0.0.1:1/", config, log=lines.append, opener=broken
        )
        assert any("browser auto-open failed" in line for line in lines)

    def test_a_declining_browser_is_one_logged_line(self, config):
        lines: list[str] = []
        _open_review_page(
            "http://127.0.0.1:1/", config, log=lines.append,
            opener=lambda _url: False,
        )
        assert any("no browser would open" in line for line in lines)
