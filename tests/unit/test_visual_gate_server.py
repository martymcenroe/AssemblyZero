"""The localhost review page and the halt-and-wake cycle (#2518).

The server carries no state -- feedback.json on disk IS the wake signal, so
these tests exercise the real thing: a real HTTP server on 127.0.0.1, a real
browser-shaped POST, a real file appearing, and wait_for_feedback waking on
it. No mocks anywhere in the cycle.
"""

from __future__ import annotations

import threading
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from assemblyzero.visual_gate import bundle as bundle_mod
from assemblyzero.visual_gate.server import serve_bundle, wait_for_feedback

PNG_1PX = (  # a real 1x1 PNG, so the page serves real image bytes
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x00\x03\x00\x01\x9d\xc0\x0e\xf5\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def round_dir(tmp_path) -> Path:
    d = tmp_path / "data" / "visual-gate" / "331" / "round-001"
    d.mkdir(parents=True)
    (d / "render-face.png").write_bytes(PNG_1PX)
    (d / "manifest.json").write_text(
        '{"values": {"band_inner": {"value": 0.88, "source": "ruling"}}}',
        encoding="utf-8",
    )
    return d


def _post(url: str, verb: str, text: str = "") -> tuple[int, bytes]:
    data = urllib.parse.urlencode({"verb": verb, "text": text}).encode()
    req = urllib.request.Request(url + "feedback", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


class TestThePage:
    def test_the_page_shows_the_image_and_the_three_verbs(self, round_dir):
        server, url = serve_bundle(round_dir, 331)
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                page = resp.read().decode("utf-8")
            assert 'src="/img/render-face.png"' in page
            for verb in ("approve", "reject", "modify"):
                assert f'value="{verb}"' in page
            assert "band_inner" in page, "the manifest values are on the page"
        finally:
            server.shutdown()

    def test_the_image_bytes_are_served_verbatim(self, round_dir):
        server, url = serve_bundle(round_dir, 331)
        try:
            with urllib.request.urlopen(url + "img/render-face.png", timeout=10) as resp:
                assert resp.read() == PNG_1PX
        finally:
            server.shutdown()

    def test_the_server_binds_localhost_only(self, round_dir):
        server, url = serve_bundle(round_dir, 331)
        try:
            assert server.server_address[0] == "127.0.0.1"
            assert url.startswith("http://127.0.0.1:")
        finally:
            server.shutdown()


class TestTheHaltAndWakeCycle:
    def test_a_submitted_verb_writes_feedback_and_wakes_the_waiter(self, round_dir):
        """The whole cycle, real: serve, POST from 'the browser', the file
        appears, the blocked waiter returns the answer."""
        server, url = serve_bundle(round_dir, 331)
        try:
            result: dict = {}

            def submit():
                status, _ = _post(url, "approve", "ship it")
                result["status"] = status

            thread = threading.Thread(target=submit)
            thread.start()
            answer = wait_for_feedback(round_dir, poll_seconds=0.05, deadline=15)
            thread.join(timeout=10)

            assert result["status"] == 200
            assert answer["verb"] == "approve"
            assert answer["text"] == "ship it"
            assert (round_dir / "feedback.json").is_file()
            assert not (round_dir / "feedback.json.tmp").exists(), (
                "the write is atomic: temp-then-rename, no half file left"
            )
        finally:
            server.shutdown()

    def test_an_answer_already_on_disk_wakes_without_a_server(self, round_dir):
        """The relaunch path: the operator answered while nothing listened;
        the resumed gate reads the answer straight off the bundle."""
        bundle_mod.write_feedback(round_dir, "modify", "band thinner")

        answer = wait_for_feedback(round_dir, poll_seconds=0.05, deadline=5)

        assert answer["verb"] == "modify"
        assert answer["text"] == "band thinner"

    def test_no_answer_times_out_only_when_a_test_deadline_asks(self, round_dir):
        with pytest.raises(TimeoutError):
            wait_for_feedback(round_dir, poll_seconds=0.05, deadline=0.3)


class TestTheServerRefusesBadSubmissions:
    def test_reject_without_words_is_refused_and_writes_nothing(self, round_dir):
        server, url = serve_bundle(round_dir, 331)
        try:
            status, body = _post(url, "reject", "")
            assert status == 400
            assert b"say why" in body
            assert not (round_dir / "feedback.json").exists()
        finally:
            server.shutdown()

    def test_an_unknown_verb_is_refused(self, round_dir):
        server, url = serve_bundle(round_dir, 331)
        try:
            status, _ = _post(url, "yolo", "whatever")
            assert status == 400
            assert not (round_dir / "feedback.json").exists()
        finally:
            server.shutdown()
