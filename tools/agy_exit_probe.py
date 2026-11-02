"""Measure whether agy exits by itself after printing its answer (#4510).

#4509 stopped the transport waiting for agy: once a finished reply has sat
unchanged for 2 s, the transport ends agy and uses the answer. That removed
the wait and left the cause unknown. This program measures it instead of
ending it. It sends prompts of increasing size through the transport's own
argv, never ends agy early, and records for each call:

- when the answer arrived, and whether and when agy exited by itself;
- what every process in agy's group was doing while it stayed alive: its
  state, kernel wait channel, threads, bytes written since the last look,
  open files under agy's home, and its established TCP connections;
- agy's own log for the call (``--log-file`` in the call's temp directory),
  and the temp files agy's summary store gained during the call.

A process still alive ``--grace`` seconds after its answer is ended, and the
row says so.

Every call is real and bounded: one agy process at a time, on a
``gemini-3.8-flash-*`` model chosen by the fleet switch's role, each written to
the model-call ledger like any other call.

Usage, from the AssemblyZero root::

    poetry run python tools/agy_exit_probe.py
    poetry run python tools/agy_exit_probe.py --sizes 2000,110000 --repeat 2 --grace 300

Results go to ``data/agy-exit-probe/<stamp>.jsonl``, one line per call, and a
table is printed at the end. A call that fails to start or returns no answer
is a failed call: the run stops, names it, and exits 1 (ADR 0236).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from assemblyzero import fleet_models
from assemblyzero.core import model_call_ledger
from assemblyzero.core.gemini_client import (
    AGY_AGENT_NAME,
    AGY_ANSWER_SETTLE_SECONDS,
    AGY_SAFETY_ARGS,
    GeminiClient,
    _agy_json_reply,
    _strip_ansi,
    write_text_only_agent,
)
from assemblyzero.utils.process import kill_process_tree

AGY_HOME = Path.home() / ".gemini" / "antigravity-cli"
DEFAULT_SIZES = (2_000, 20_000, 50_000, 80_000, 110_000)
ALLOWED_MODEL_PREFIX = "gemini-3.8-flash-"
POLL_SECONDS = 0.25
#: Seconds after the answer at which a still-living agy is examined.
SNAPSHOT_AT = (5.0, 30.0, 90.0, 180.0)
FILLER_LINE = "Line {n:06d}: hourly load, price and status recorded for the grid model.\n"
SYSTEM_INSTRUCTION = "You answer in one short sentence."
#: For a long reply. The short instruction made the model refuse to write the
#: code it was asked for (2026-11-02), which measured nothing.
LONG_SYSTEM_INSTRUCTION = "You write exactly what the request asks for."
INSTRUCTION = (
    "Below are numbered lines of filler text. Reply with one short sentence "
    "that states the number of the last line. Do not repeat the lines.\n\n"
)
#: The instruction when a long reply is wanted: the real calls #4509 measured
#: returned whole files. Asked to copy filler lines back, the model declined
#: and answered in a sentence (2026-11-02, 16 calls), so it is asked for code.
COPY_INSTRUCTION = (
    "Ignore the numbered filler lines below. Write a Python module of {k} "
    "functions named f_1 to f_{k}, each with a one-line docstring and returning "
    "its own number. Write only the code, with no explanation.\n\n"
)


def instruction_for(reply_lines: int) -> str:
    return COPY_INSTRUCTION.format(k=reply_lines) if reply_lines else INSTRUCTION


def build_content(size: int, reply_lines: int = 0) -> str:
    """Exactly ``size`` characters: the instruction, then numbered filler lines."""
    instruction = instruction_for(reply_lines)
    if size <= len(instruction):
        raise ValueError(f"size {size} is too small to carry the instruction")
    lines: list[str] = []
    total = len(instruction)
    n = 1
    while total < size:
        line = FILLER_LINE.format(n=n)
        lines.append(line)
        total += len(line)
        n += 1
    return (instruction + "".join(lines))[:size]


def compose_prompt(model: str, content: str, long_reply: bool = False) -> str:
    """The prompt as ``GeminiClient._invoke_via_cli`` composes it."""
    return (
        f"You are {model}.\n\n"
        f"<system_instruction>\n{LONG_SYSTEM_INSTRUCTION if long_reply else SYSTEM_INSTRUCTION}"
        "\n</system_instruction>\n\n"
        f"<user_content>\n{content}\n</user_content>"
    )


def parse_stat(text: str) -> dict:
    """The fields of ``/proc/<pid>/stat`` this program reads.

    The command name is inside parentheses and may itself contain spaces or
    parentheses, so the fields are counted from the LAST closing parenthesis.
    """
    open_at = text.index("(")
    close_at = text.rindex(")")
    rest = text[close_at + 2:].split()
    return {
        "pid": int(text[:open_at].strip()),
        "comm": text[open_at + 1:close_at],
        "state": rest[0],
        "ppid": int(rest[1]),
        "pgrp": int(rest[2]),
        "threads": int(rest[17]),
    }


def parse_tcp_table(text: str) -> dict[str, dict]:
    """Socket inode to endpoints, from ``/proc/<pid>/net/tcp`` or ``tcp6``."""
    rows: dict[str, dict] = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        rows[parts[9]] = {"local": parts[1], "remote": parts[2], "state": parts[3]}
    return rows


def hex_endpoint(endpoint: str) -> str:
    """``0100007F:1F90`` to ``127.0.0.1:8080`` (IPv4); IPv6 is left in hex."""
    address, port = endpoint.split(":")
    if len(address) == 8:
        octets = [str(int(address[i:i + 2], 16)) for i in (6, 4, 2, 0)]
        return f"{'.'.join(octets)}:{int(port, 16)}"
    return f"[{address}]:{int(port, 16)}"


#: TCP states in /proc/net/tcp, the ones worth naming.
TCP_STATES = {"01": "ESTABLISHED", "06": "TIME_WAIT", "08": "CLOSE_WAIT", "0A": "LISTEN"}


def _read(path: Path) -> str:
    """A ``/proc`` or log file, or "" when it is gone.

    A process can exit between listing ``/proc`` and reading it, which is an
    answer, not a failure. A missing agy log shows in the row as ``log_lines: 0``.
    """
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def group_members(pgid: int) -> list[dict]:
    """Every process whose process group is ``pgid``."""
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        text = _read(entry / "stat")
        if not text:
            continue
        stat = parse_stat(text)
        if stat["pgrp"] == pgid:
            members.append(stat)
    return members


def write_bytes(pid: int) -> int | None:
    for line in _read(Path(f"/proc/{pid}/io")).splitlines():
        if line.startswith("write_bytes:"):
            return int(line.split(":")[1])
    return None


def describe(pid: int, last_writes: dict[int, int]) -> dict:
    """What one process is doing: wait channel, writes since last look, files, sockets."""
    proc = Path(f"/proc/{pid}")
    files, sockets, pipes = [], [], 0
    fd_dir = proc / "fd"
    try:
        fds = list(fd_dir.iterdir())
    except OSError:
        fds = []
    for fd in fds:
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("socket:["):
            sockets.append(target[len("socket:["):-1])
        elif target.startswith("pipe:"):
            pipes += 1
        elif target.startswith((str(AGY_HOME), "/tmp")):
            files.append(target)
    tcp = {**parse_tcp_table(_read(proc / "net" / "tcp")),
           **parse_tcp_table(_read(proc / "net" / "tcp6"))}
    connections = sorted(
        f"{hex_endpoint(tcp[i]['remote'])} {TCP_STATES.get(tcp[i]['state'], tcp[i]['state'])}"
        for i in sockets if i in tcp
    )
    written = write_bytes(pid)
    delta = None if written is None else written - last_writes.get(pid, written)
    if written is not None:
        last_writes[pid] = written
    return {
        "wchan": _read(proc / "wchan").strip(),
        "write_bytes_since_last": delta,
        "pipes": pipes,
        "sockets": len(sockets),
        "tcp": connections,
        "agy_files": sorted(files),
    }


def agy_log_files() -> set[Path]:
    """agy's per-process log files; each agy process starts a new one."""
    try:
        return set((AGY_HOME / "log").glob("cli-*.log"))
    except OSError:
        return set()


def store_temp_files() -> set[str]:
    """Temp files beside agy's summary store; a write in progress leaves one."""
    try:
        return {p.name for p in AGY_HOME.iterdir() if p.name.endswith(".tmp")}
    except OSError:
        return set()


def log_tail_after_answer(log_text: str, limit: int = 25) -> list[str]:
    """agy's log lines from the completion signal on, which is where #4509 lost it."""
    lines = log_text.splitlines()
    for i, line in enumerate(lines):
        if "sending completion signal" in line:
            return lines[i:i + limit]
    return lines[-limit:]


def one_call(
    client: GeminiClient, size: int, grace: float, reply_lines: int = 0, own_log: bool = False,
) -> dict:
    """One agy process, watched and never ended before ``grace`` after its answer."""
    prompt = compose_prompt(client.model, build_content(size, reply_lines), reply_lines > 0)
    temps_before = store_temp_files()
    row: dict = {"size_chars": size, "reply_lines": reply_lines,
                 "prompt_chars": len(prompt), "model": client.model}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        write_text_only_agent(tmp)
        reply_path = Path(tmp) / "agy-reply.out"
        log_path = Path(tmp) / "agy-call.log"
        with reply_path.open("wb") as sink:
            # The transport's exact argv by default. --own-log adds --log-file,
            # which moves agy's log into this call's directory and so is not
            # the call the pipeline makes.
            tail = ["--log-file", str(log_path)] if own_log else []
            logs_before = agy_log_files()
            proc = subprocess.Popen(
                client._agy_argv(
                    tmp, "--agent", AGY_AGENT_NAME, *AGY_SAFETY_ARGS,
                    "--model", client.model, "--output-format", "json", *tail,
                ),
                stdin=subprocess.PIPE, stdout=sink, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", cwd=tmp,
                start_new_session=True,
            )
        stderr_chunks: list[str] = []

        def feed() -> None:
            try:
                proc.stdin.write(prompt)
                proc.stdin.close()
            except OSError as exc:
                stderr_chunks.append(f"[probe] stdin write failed: {exc}")

        def drain() -> None:
            stderr_chunks.append(proc.stderr.read())

        threading.Thread(target=feed, daemon=True).start()
        drainer = threading.Thread(target=drain, daemon=True)
        drainer.start()

        size_seen, changed_at, answered_at = 0, time.monotonic(), None
        snapshots: list[dict] = []
        last_writes: dict[int, int] = {}
        pending = list(SNAPSHOT_AT)
        temps_seen: set[str] = set()
        ended_by_probe = False
        while True:
            now = time.monotonic()
            if proc.poll() is not None:
                break
            current = reply_path.stat().st_size
            if current != size_seen:
                size_seen, changed_at = current, now
            elif answered_at is None and size_seen and now - changed_at >= AGY_ANSWER_SETTLE_SECONDS:
                text = _strip_ansi(reply_path.read_bytes().decode("utf-8", errors="replace")).strip()
                if text.startswith("{") and text.endswith("}"):
                    answered_at = changed_at
            if answered_at is not None:
                temps_seen |= store_temp_files() - temps_before
                since = now - answered_at
                while pending and since >= pending[0]:
                    at = pending.pop(0)
                    snapshots.append({
                        "after_answer_s": at,
                        "processes": [
                            {**m, **describe(m["pid"], last_writes)}
                            for m in group_members(proc.pid)
                        ],
                    })
                if since >= grace:
                    kill_process_tree(proc.pid)
                    proc.wait(timeout=30)
                    ended_by_probe = True
                    break
            elif now - started > 600:
                kill_process_tree(proc.pid)
                proc.wait(timeout=30)
                ended_by_probe = True
                break
            time.sleep(POLL_SECONDS)
        exited_at = time.monotonic()
        if answered_at is None and size_seen:
            # It exited inside the settle window: the answer is its last write,
            # to within one poll.
            answered_at = changed_at
        drainer.join(timeout=10)
        reply_text = _strip_ansi(reply_path.read_bytes().decode("utf-8", errors="replace")).strip()
        if own_log:
            log_text, log_source = _read(log_path), "own --log-file"
        else:
            # The log agy started for this process. Another agy starting at the
            # same moment would make this ambiguous, so the row says how many.
            new_logs = sorted(agy_log_files() - logs_before)
            log_text = "\n".join(_read(p) for p in new_logs)
            log_source = f"{len(new_logs)} new file(s) in {AGY_HOME / 'log'}"

    reply = _agy_json_reply(reply_text)
    row.update({
        "answer_s": None if answered_at is None else round(answered_at - started, 1),
        "status": None if reply is None else reply.get("status"),
        "response": None if reply is None else str(reply.get("response", ""))[:200],
        "usage": None if reply is None else reply.get("usage"),
        "exited_by_itself": not ended_by_probe,
        "returncode": proc.returncode,
        "alive_after_answer_s": (
            None if answered_at is None else round(exited_at - answered_at, 1)
        ),
        "wall_s": round(exited_at - started, 1),
        "snapshots": snapshots,
        "store_temp_files_during_call": sorted(temps_seen),
        "store_temp_files_left": sorted(store_temp_files() - temps_before),
        "log_after_answer": log_tail_after_answer(log_text),
        "log_lines": len(log_text.splitlines()),
        "log_source": log_source,
        "argv_has_log_file": own_log,
        "stderr": "".join(stderr_chunks)[-800:],
    })
    ok = reply is not None and reply.get("status") == "SUCCESS"
    model_call_ledger.record(
        "tools.agy_exit_probe", "agy", client.model, row["usage"],
        row["wall_s"], "ok" if ok else "failed",
        None if ok else f"no SUCCESS reply: {reply_text[:200]!r}",
    )
    return row


def through_transport(client: GeminiClient, size: int, reply_lines: int) -> dict:
    """One call through the transport itself, watcher and all (#4510 T3).

    Records whether the watcher ended agy, which is what its "has not exited"
    warning says, and the call's own result.
    """
    import logging

    from assemblyzero.core import gemini_client

    seen: list[str] = []

    class Catch(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record.getMessage())

    handler = Catch(level=logging.WARNING)
    gemini_client.logger.addHandler(handler)
    started = time.monotonic()
    try:
        ok, text, error = client._invoke_via_stdin(
            compose_prompt(client.model, build_content(size, reply_lines), reply_lines > 0))
    finally:
        gemini_client.logger.removeHandler(handler)
    return {
        "size_chars": size, "reply_lines": reply_lines, "ok": ok,
        "error": error[:300], "reply_chars": len(text),
        "wall_s": round(time.monotonic() - started, 1),
        "watcher_ended_agy": any("has not exited" in m for m in seen),
        "settle_s": gemini_client.AGY_ANSWER_SETTLE_SECONDS,
    }


def log_clock(line: str) -> str | None:
    """``HH:MM:SS`` from a glog line such as ``I1101 17:16:00.463432 ...``."""
    parts = line.split()
    if len(parts) > 1 and len(parts[0]) == 5 and parts[0][0] in "IWEF":
        return parts[1][:8]
    return None


def read_agy_log(path: Path) -> dict:
    """What one agy process's log says about its end."""
    lines = _read(path).splitlines()
    clocks = [c for c in (log_clock(line) for line in lines) if c]
    signal_at = reconciled_at = None
    for line in lines:
        if signal_at is None and "sending completion signal" in line:
            signal_at = log_clock(line)
        if reconciled_at is None and "reconciliation complete" in line:
            reconciled_at = log_clock(line)
    return {
        "log": path.name,
        "start": clocks[0] if clocks else None,
        "end": clocks[-1] if clocks else None,
        "answered_at": signal_at,
        "reconciled_at": reconciled_at,
        "lock_errors": sum("database is locked" in line for line in lines),
        "last_line": lines[-1][:160] if lines else "",
    }


def analyze_logs(prefix: str) -> int:
    """One row per agy log whose name starts ``cli-<prefix>``, with the overlap."""
    paths = sorted((AGY_HOME / "log").glob(f"cli-{prefix}*.log"))
    rows = [read_agy_log(p) for p in paths]
    for row in rows:
        row["alive_beside_it"] = sum(
            1 for other in rows
            if other is not row and other["start"] and other["end"] and row["start"]
            and row["end"] and other["start"] <= row["end"] and row["start"] <= other["end"]
        )
        print(json.dumps(row))
    print(f"{len(rows)} logs", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--logs", metavar="PREFIX",
                        help="make no call: read agy's logs named cli-PREFIX*, such as "
                             "20261101_17, and print one row per process")
    parser.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES),
                        help="comma-separated prompt sizes in characters")
    parser.add_argument("--reply-lines", default="0",
                        help="comma-separated reply lengths, in filler lines the model "
                             "copies back (0: a one-sentence reply); every size runs "
                             "with every length")
    parser.add_argument("--repeat", type=int, default=1, help="calls per size")
    parser.add_argument("--grace", type=float, default=240.0,
                        help="seconds after the answer before a living agy is ended")
    parser.add_argument("--through-transport", action="store_true",
                        help="call through GeminiClient's transport, watcher and all, "
                             "and record whether the watcher ended agy (#4510 T3)")
    parser.add_argument("--own-log", action="store_true",
                        help="add --log-file in the call's directory; off by default, "
                             "so the argv is the transport's own")
    parser.add_argument("--role", default="workflow",
                        help="the fleet switch role whose model is used")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.logs:
        return analyze_logs(args.logs)

    model = fleet_models.model_for(args.role)
    if model.provider != "agy" or not model.id.startswith(ALLOWED_MODEL_PREFIX):
        print(f"ERROR: role {args.role!r} plays {model.id} on {model.provider}; this "
              f"probe runs only {ALLOWED_MODEL_PREFIX}* on agy (#4510)", file=sys.stderr)
        return 1
    client = GeminiClient(model=model.id)
    if not client._agy_cli:
        print("ERROR: agy not found", file=sys.stderr)
        return 1
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    out = args.out or REPO_ROOT / "data" / "agy-exit-probe" / (
        datetime.now().astimezone().strftime("%Y%m%d-%H%M%S") + ".jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    reply_lengths = [int(k) for k in args.reply_lines.split(",") if k.strip()]

    if args.through_transport:
        ended = 0
        for size in sizes:
            for reply_lines in reply_lengths:
                for _ in range(args.repeat):
                    row = through_transport(client, size, reply_lines)
                    with out.open("a", encoding="utf-8", newline="\n") as fh:
                        fh.write(json.dumps(row) + "\n")
                    print(json.dumps(row), flush=True)
                    if not row["ok"]:
                        print(f"ERROR: the call failed: {row['error']}", file=sys.stderr)
                        return 1
                    ended += row["watcher_ended_agy"]
        print(f"\nThe watcher ended agy on {ended} call(s). Rows: {out}")
        return 0

    rows = []
    for size in sizes:
        for reply_lines in reply_lengths:
            for attempt in range(1, args.repeat + 1):
                print(f"[probe] {size:,} chars, reply {reply_lines} lines, call "
                      f"{attempt} of {args.repeat} ...", flush=True)
                row = one_call(client, size, args.grace, reply_lines, args.own_log)
                row["attempt"] = attempt
                rows.append(row)
                with out.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(row) + "\n")
                print(f"[probe]   answer {row['answer_s']} s, status {row['status']}, "
                      f"exited by itself {row['exited_by_itself']}, alive after answer "
                      f"{row['alive_after_answer_s']} s", flush=True)
                if row["status"] != "SUCCESS":
                    print(f"ERROR: the {size:,}-char call returned no SUCCESS reply; "
                          f"stopping. {len(rows) - 1} calls succeeded before it. "
                          f"Rows: {out}", file=sys.stderr)
                    return 1

    print(f"\n{'chars':>9} {'reply ln':>9} {'answer s':>9} {'exited':>7} {'alive after s':>14}")
    for row in rows:
        print(f"{row['size_chars']:>9,} {row['reply_lines']:>9} {row['answer_s']!s:>9} "
              f"{'yes' if row['exited_by_itself'] else 'no':>7} "
              f"{row['alive_after_answer_s']!s:>14}")
    print(f"\nRows: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
