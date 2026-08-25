"""The localhost review page (#2518): the picture, three verbs, a text box.

stdlib http.server, bound to 127.0.0.1 only, ephemeral port. No framework, no
network exposure -- the operator-ratified design names both constraints.

Submitting writes ``feedback.json`` beside the bundle (atomically, via
bundle.write_feedback) and the page says so; the serving run wakes on the
file's appearance. The server carries no state of its own -- the bundle dir
is the state, which is what makes a killed run resumable: the answer is on
disk regardless of who was listening when it was given.
"""

from __future__ import annotations

import html
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from assemblyzero.visual_gate import bundle as bundle_mod

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Visual gate — issue #{issue}</title>
<style>
 body {{ background:#141416; color:#e8e8ea; font-family:Segoe UI,sans-serif;
        max-width:1100px; margin:2rem auto; padding:0 1rem; }}
 img  {{ max-width:100%; border:1px solid #333; margin:.5rem 0; }}
 textarea {{ width:100%; min-height:7rem; background:#1d1d20; color:#e8e8ea;
        border:1px solid #444; padding:.5rem; font-size:1rem; }}
 button {{ font-size:1.05rem; padding:.55rem 1.6rem; margin:.6rem .6rem 0 0;
        border:0; border-radius:4px; cursor:pointer; }}
 .approve {{ background:#2e7d32; color:#fff; }}
 .reject  {{ background:#b03030; color:#fff; }}
 .modify  {{ background:#2a5db0; color:#fff; }}
 .meta {{ color:#9a9aa0; font-size:.9rem; white-space:pre-wrap; }}
</style></head><body>
<h1>Visual gate — issue #{issue}, {round_name}</h1>
<p>Rendered directly from the binding contract. Approve stamps this render
and the run proceeds; Reject halts for redesign; Modify turns each line of
your feedback into a contract delta and re-renders.</p>
{images}
<form method="post" action="/feedback">
<textarea name="text" placeholder="Feedback — one item per line works best. Required for Reject and Modify."></textarea><br>
<button class="approve" name="verb" value="approve">Approve</button>
<button class="reject" name="verb" value="reject">Reject</button>
<button class="modify" name="verb" value="modify">Modify</button>
</form>
<h2>Contract values behind this render</h2>
<div class="meta">{manifest}</div>
</body></html>"""

_DONE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Recorded</title></head>
<body style="background:#141416;color:#e8e8ea;font-family:Segoe UI,sans-serif;
             max-width:700px;margin:3rem auto;">
<h1>{verb} recorded</h1>
<p>feedback.json is written beside the bundle; the run takes it from here.
This page can be closed.</p></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    # Set per-server via functools.partial-style subclassing in serve_bundle.
    round_dir: Path
    issue: int

    def log_message(self, *_args):  # quiet: the run log is the narration
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (http.server API)
        images = bundle_mod.bundle_images(self.round_dir)
        if self.path.startswith("/img/"):
            name = self.path[len("/img/"):]
            match = next((p for p in images if p.name == name), None)
            if match is None:
                self._send(404, b"no such image", "text/plain")
                return
            self._send(200, match.read_bytes(), "image/png")
            return
        manifest_path = self.round_dir / "manifest.json"
        manifest = (
            manifest_path.read_text(encoding="utf-8")
            if manifest_path.is_file() else "(no manifest)"
        )
        img_tags = "\n".join(
            f'<h3>{html.escape(p.name)}</h3><img src="/img/{html.escape(p.name)}" alt="{html.escape(p.name)}">'
            for p in images
        )
        page = _PAGE.format(
            issue=self.issue,
            round_name=self.round_dir.name,
            images=img_tags or "<p><b>No images in bundle.</b></p>",
            manifest=html.escape(manifest),
        )
        self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self):  # noqa: N802
        if self.path != "/feedback":
            self._send(404, b"unknown endpoint", "text/plain")
            return
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        verb = (form.get("verb") or [""])[0]
        text = (form.get("text") or [""])[0]
        if verb not in bundle_mod.VERBS:
            self._send(400, b"unknown verb", "text/plain")
            return
        if verb in ("reject", "modify") and not text.strip():
            self._send(
                400,
                b"Reject and Modify need words in the text box - go back and say why.",
                "text/plain",
            )
            return
        bundle_mod.write_feedback(self.round_dir, verb, text)
        self._send(200, _DONE.format(verb=verb.capitalize()).encode("utf-8"),
                   "text/html; charset=utf-8")


def serve_bundle(round_dir: Path, issue: int) -> tuple[ThreadingHTTPServer, str]:
    """Serve one round's bundle on 127.0.0.1:<ephemeral>. Returns (server, url).

    The caller owns shutdown. Binding to port 0 lets the OS pick a free port,
    so two gates (or a gate and a stale orphan) never fight over one.
    """
    handler = type("BoundHandler", (_Handler,), {
        "round_dir": round_dir, "issue": issue,
    })
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def wait_for_feedback(
    round_dir: Path, *, poll_seconds: float = 2.0,
    reminder_every: float = 300.0, log=print, deadline: float | None = None,
) -> dict:
    """Block until feedback.json appears, then return it.

    No timeout that overrides the human (house rule): the default waits
    forever, reminding every five minutes. ``deadline`` exists for tests.
    """
    start = time.monotonic()
    last_reminder = start
    while True:
        answer = bundle_mod.read_feedback(round_dir)
        if answer is not None:
            return answer
        now = time.monotonic()
        if deadline is not None and now - start > deadline:
            raise TimeoutError(f"no feedback.json in {round_dir} after {deadline}s")
        if now - last_reminder >= reminder_every:
            # #2520: say the URL, every time. The first live serve printed a
            # path to the JSON holding the URL, and the operator spent 26
            # minutes staring at the indirection. In a detached run these
            # lines are the only surface -- each one must be actionable on
            # sight, with the file kept as the machine-readable copy.
            log(
                f"    [visual] still waiting on operator feedback -- open "
                f"{pending_url(round_dir) or 'the review page'} "
                f"({round_dir.name})"
            )
            last_reminder = now
        time.sleep(poll_seconds)


def pending_url(round_dir: Path) -> str:
    """The served page's URL, from the round's own sentinel; "" if unknowable.

    The sentinel stays the machine-readable home of the URL (#2520) -- this
    is the one reader, shared by the waiting line and the launcher-side
    announcement, so the two surfaces can never disagree.
    """
    import json

    path = round_dir / "feedback-pending.json"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("url", ""))
    except (OSError, ValueError):
        # fail-open: "" is this function's documented "unknowable" answer --
        # the waiting line falls back to naming the review page generically,
        # and a reminder must never crash the wait it decorates (#2520).
        return ""
