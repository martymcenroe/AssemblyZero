#!/usr/bin/env python3
"""Store the pr-sentinel App's private key encrypted, once GitHub accepts it (#4784).

`new_repo.py` checks that the pr-sentinel App is installed on a new repository
(#1822). To ask GitHub as the App, it decrypts `~/.secrets/pr-sentinel-app.gpg`,
which holds the App ID on its first line and the App's private key after it.
Without that file the check is skipped. This program makes the file from a key
downloaded from the App's settings page, by the rules of ADR-0227: the key reaches
gpg through a pipe, never through argv, the environment or a plaintext file, and
every surface it passed through gets a step.

Only the operator runs it, in his own terminal. An agent never does, not even
bare: the dry run reads the key into the process to prove it with GitHub, and
gpg's passphrase box is his to answer.

## Usage

In bash, from any folder. `<AssemblyZero>` stands for the absolute path of the
AssemblyZero checkout (a test forbids spelling the Projects root, #3609), and
`<key file>` for the absolute path of the `.pem` that the App's settings page
downloaded (Private keys, Generate a private key). The dry run prints the
--apply command with both filled in.

    poetry -C <AssemblyZero> run python <AssemblyZero>/tools/store_pr_sentinel_app_key.py --pem <key file>
    poetry -C <AssemblyZero> run python <AssemblyZero>/tools/store_pr_sentinel_app_key.py --pem <key file> --apply

The first checks everything and changes nothing. The second stores the key and
removes the downloaded file.

It runs on Ubuntu and on Windows (Git Bash), and writes to the home folder of the
side it runs on. It removes the key file it stored, so for the other side,
generate another key on the same page: an App accepts several keys at once.

## What one run does

  1. Refuses to run as root.
  2. Reads the App ID from config/fleet-ids.json (`pr_sentinel_app_id`). It is
     public, so nothing asks for it.
  3. Checks --pem: an absolute path to a regular file, not a symbolic link and with
     no second hard link (removing one name must remove the key), holding one PEM
     block that loads as an RSA private key with no passphrase.
  4. Checks --out (default `~/.secrets/pr-sentinel-app.gpg`): an absolute path
     where nothing exists yet, and nothing at `<out>.tmp` either. It never
     overwrites a file.
  5. Proves the key with GitHub: mints an App JWT from the App ID and the key and
     asks `GET https://api.github.com/app`, which must answer 200 with this App's
     id. A 401 means GitHub does not accept the key: generate a fresh one.
  6. Prints the plan.
  7. Without --apply, prints the --apply command and ends
     `OK: dry run, nothing changed`.
  8. With --apply:
     a. makes the folder of --out with mode 700 if it is missing;
     b. runs `gpg --symmetric` with the App ID, a newline and the key on its
        standard input, writing `<out>.tmp`; gpg's passphrase box asks for a new
        passphrase;
     c. sets `<out>.tmp` to mode 600;
     d. decrypts `<out>.tmp` as new_repo.py will
        (`_pat_session.pr_sentinel_app_session`, which asks for the passphrase
        again) and checks that it gives back exactly what went in; prints the App
        ID and the key's first line, nothing more;
     e. renames `<out>.tmp` to `<out>`;
     f. removes the key file and checks that it is gone.
  9. Lists what is left for his own hand: the browser's download history, the
     Recycle Bin, and any other copy of the key.

A failure in 8b to 8e removes `<out>.tmp`, which holds only ciphertext, and keeps
the key file. The key file is removed only after the check in 8d passes, so a
file stored with a mistyped passphrase never costs him the key.

The key and the bundle live only in this process's memory. Python cannot wipe a
string, so the protection is the process's scope: it ends when the run does.

The last line is `OK: ...` with exit 0, or
`FAILED: <step>: <reason>. Nothing after this step was done. Paste this output to
the agent.` with exit 1. No line carries the key.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

try:
    import _github_app_jwt
    import _pat_session
    import fleet_ids
except ImportError:
    # Fallback if running from a different directory
    sys.path.insert(0, str(Path(__file__).parent))
    import _github_app_jwt
    import _pat_session
    import fleet_ids

GITHUB_APP_URL = "https://api.github.com/app"
GITHUB_TIMEOUT_S = 30
SECRET_NAME = _pat_session.SECRET_PR_SENTINEL_APP
FRESH_KEY = (
    "Generate a fresh key on the App's settings page on GitHub (Private keys, "
    "Generate a private key) and run this again with the new file"
)


class Refused(Exception):
    """A step that cannot go on. Carries the step's name and the reason."""

    def __init__(self, step: str, reason: str) -> None:
        super().__init__(f"{step}: {reason}")
        self.step = step
        self.reason = reason


def _fail(step: str, reason: str) -> int:
    print(f"FAILED: {step}: {reason}. Nothing after this step was done. Paste this output to the agent.")
    return 1


def _check_user() -> str:
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None:
        return "this OS has no user id to check; not root"
    uid = geteuid()
    if uid == 0:
        raise Refused("refuse root", "running as root; run it as yourself, without sudo")
    return f"running as user id {uid}, not root"


def _app_id() -> str:
    """The pr-sentinel App ID, from config/fleet-ids.json. Public, so never asked for."""
    try:
        app_id = fleet_ids.get("pr_sentinel_app_id")
    except (OSError, KeyError, ValueError) as e:
        raise Refused("read the App ID", f"config/fleet-ids.json gave no pr_sentinel_app_id ({e})") from e
    if not app_id.isdigit():
        raise Refused("read the App ID", f"pr_sentinel_app_id is {app_id!r}, not a number")
    return app_id


def _read_pem(given: str) -> tuple[Path, str, int]:
    """The key file's path, its PEM text with LF line ends, and the key's size in bits."""
    step = "check --pem"
    path = Path(given)
    if not path.is_absolute():
        raise Refused(step, f"{given} is not an absolute path")
    if path.is_symlink():
        raise Refused(step, f"{path} is a symbolic link; give the key file itself, so that the file removed is the key")
    try:
        info = path.stat()
    except FileNotFoundError as e:
        raise Refused(step, f"{path} does not exist") from e
    except OSError as e:
        raise Refused(step, f"{path} could not be read ({e.strerror or type(e).__name__})") from e
    if not stat.S_ISREG(info.st_mode):
        raise Refused(step, f"{path} is not a regular file")
    if info.st_nlink > 1:
        raise Refused(
            step,
            f"{path} has {info.st_nlink} names on disk (hard links); removing this one "
            "would leave the key readable under another",
        )
    try:
        data = path.read_bytes()
    except OSError as e:
        raise Refused(step, f"{path} could not be read ({e.strerror or type(e).__name__})") from e
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as e:
        raise Refused(step, f"{path} is not a PEM file: it is not plain ASCII text") from e
    pem = text.replace("\r\n", "\n").strip() + "\n"
    one_block = (
        pem.startswith("-----BEGIN ")
        and pem.rstrip("\n").endswith("PRIVATE KEY-----")
        and pem.count("-----BEGIN ") == 1
    )
    if not one_block:
        raise Refused(step, f"{path} is not a PEM file holding one private key")
    try:
        key = serialization.load_pem_private_key(pem.encode("ascii"), password=None)
    except TypeError as e:
        raise Refused(step, f"{path} is protected by a passphrase; give the key as GitHub downloaded it") from e
    except (ValueError, UnsupportedAlgorithm) as e:
        raise Refused(step, f"{path} does not load as a private key ({e})") from e
    if not isinstance(key, rsa.RSAPrivateKey):
        raise Refused(step, f"{path} is not an RSA key, and a GitHub App key is")
    return path, pem, key.key_size


def _check_out(given: str) -> tuple[Path, Path, str]:
    """--out, its .tmp beside it, and what will happen to its folder."""
    step = "check --out"
    out = Path(given)
    if not out.is_absolute():
        raise Refused(step, f"{given} is not an absolute path")
    tmp = out.with_name(out.name + ".tmp")
    if os.path.lexists(out):
        raise Refused(step, f"{out} already exists, and this program never overwrites it")
    if os.path.lexists(tmp):
        raise Refused(
            step,
            f"{tmp} already exists, probably left by an earlier run that was stopped; "
            "look at it and remove it, then run this again",
        )
    folder = out.parent
    if folder.is_dir():
        said = f"its folder {folder} exists"
    elif os.path.lexists(folder):
        raise Refused(step, f"{folder} exists and is not a folder")
    else:
        said = f"its folder {folder} will be made with mode 700"
    return out, tmp, said


def _github_message(body: bytes) -> str:
    try:
        answer = json.loads(body)
    except ValueError:
        answer = None
    if isinstance(answer, dict) and answer.get("message"):
        return str(answer["message"])
    text = body.decode("utf-8", errors="replace").strip()
    return text[:200] if text else "no message"


def _prove_with_github(app_id: str, pem: str) -> str:
    """GET /app as the App. It must answer 200 with this App's id (#4784, requirement 6)."""
    step = "prove the key with GitHub"
    try:
        token = _github_app_jwt.mint_app_jwt(app_id, pem)
    except (ValueError, TypeError, UnsupportedAlgorithm) as e:
        raise Refused(step, f"could not sign a token with the key ({e})") from e
    request = urllib.request.Request(
        GITHUB_APP_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "assemblyzero-store-pr-sentinel-app-key",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_TIMEOUT_S) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, (e.read() if e.fp is not None else b"")
    except OSError as e:
        raise Refused(step, f"could not reach {GITHUB_APP_URL} ({getattr(e, 'reason', e)})") from e
    if status == 401:
        raise Refused(
            step,
            f"GitHub answered 401 ({_github_message(body)}): GitHub does not accept this key. "
            f"{FRESH_KEY}. The key file is left where it is",
        )
    if status != 200:
        raise Refused(step, f"GitHub answered {status} ({_github_message(body)})")
    try:
        answer = json.loads(body)
    except ValueError as e:
        raise Refused(step, "GitHub answered 200 with a body that is not JSON") from e
    got = answer.get("id") if isinstance(answer, dict) else None
    if str(got) != app_id:
        raise Refused(
            step,
            f"GitHub answered 200 for App id {got}, not {app_id}: this key belongs to another App. "
            "Download a key from the pr-sentinel App's settings page",
        )
    name = answer.get("slug") or answer.get("name") or "no name given"
    return f"GitHub answered 200 to GET {GITHUB_APP_URL} as App {app_id} ({name})"


def _gpg_env() -> dict[str, str]:
    """This process's environment, plus GPG_TTY on Ubuntu (#4179).

    gpg's standard input carries the bundle, so pinentry-curses cannot find the
    terminal there; GPG_TTY names it. It names a device and carries no secret.
    """
    env = dict(os.environ)
    if sys.platform != "win32":
        terminal = _pat_session._terminal()
        if terminal:
            env["GPG_TTY"] = terminal
    return env


def _encrypt(bundle: bytes, tmp: Path) -> None:
    """gpg --symmetric, the bundle on its standard input, the ciphertext to `tmp`."""
    step = "encrypt"
    command = [
        "gpg", "--batch", "--pinentry-mode", "ask", "--no-symkey-cache",
        "--symmetric", "--cipher-algo", "AES256", "--output", str(tmp),
    ]
    try:
        result = subprocess.run(
            command,
            input=bundle,
            capture_output=True,
            env=_gpg_env(),
            timeout=_pat_session.GPG_TIMEOUT_S,
            check=False,
        )
    except OSError as e:
        raise Refused(step, f"gpg could not be started ({e.strerror or type(e).__name__}); is it installed?") from e
    if result.returncode != 0:
        said = result.stderr.decode("utf-8", errors="replace").strip()
        try:
            _pat_session._stop_if_no_prompt(said, SECRET_NAME)
        except _pat_session.PinentryUnavailable as e:
            raise Refused(step, str(e)) from e
        if "cancel" in said.lower():
            raise Refused(step, "the passphrase box was cancelled; nothing was stored")
        raise Refused(step, f"gpg exited {result.returncode}: {said or 'no message'}")
    if not tmp.is_file():
        raise Refused(step, f"gpg exited 0 but wrote no {tmp}")


def _set_mode(tmp: Path) -> str:
    step = "set the mode"
    try:
        os.chmod(tmp, 0o600)
    except OSError as e:
        raise Refused(step, f"{tmp} could not be set to mode 600 ({e.strerror or type(e).__name__})") from e
    if sys.platform == "win32":
        return f"{tmp} is under your user folder; Windows has no mode 600 to set"
    mode = stat.S_IMODE(tmp.stat().st_mode)
    if mode != 0o600:
        raise Refused(step, f"{tmp} is mode {mode:o} after chmod 600; its disk does not keep modes")
    return f"{tmp} is mode 600"


def _check_file(tmp: Path, bundle: str) -> tuple[str, str]:
    """Decrypt `tmp` as new_repo.py will, and compare. The App ID and the PEM's first line."""
    step = "check the file"
    try:
        with _pat_session.pr_sentinel_app_session(
            tmp, reason="check the file just written, before the key file is removed"
        ) as decrypted:
            if decrypted == bundle.strip():
                lines = decrypted.split("\n")
                return lines[0], lines[1]
    except RuntimeError as e:
        raise Refused(step, f"{tmp} could not be decrypted ({e}); the key file is kept") from e
    raise Refused(
        step,
        f"decrypting {tmp} did not give back the App ID and key that went in; the key file is kept",
    )


def _store(bundle: str, out: Path, tmp: Path) -> tuple[str, str]:
    """Steps 8a to 8e. Any way out before the rename removes `tmp`, which holds only ciphertext."""
    folder = out.parent
    if folder.is_dir():
        print(f"Step 8a, folder: {folder} exists.")
    else:
        try:
            folder.mkdir(mode=0o700, parents=True)
            os.chmod(folder, 0o700)
        except OSError as e:
            raise Refused("make the folder", f"{folder} could not be made ({e.strerror or type(e).__name__})") from e
        print(f"Step 8a, folder: {folder} made with mode 700.")

    stored = False
    try:
        bar = "=" * 64
        print(bar, file=sys.stderr, flush=True)
        print("NEW PASSPHRASE -- gpg's box is about to ask you to choose one", file=sys.stderr)
        print(f"  secret : {SECRET_NAME}", file=sys.stderr)
        print(f"  file   : {tmp}", file=sys.stderr)
        print("  Type it as often as the box asks. new_repo.py asks for it on every run.", file=sys.stderr)
        print(bar, file=sys.stderr, flush=True)
        _encrypt(bundle.encode("ascii"), tmp)
        print(f"Step 8b, encrypt: gpg wrote {tmp}.", flush=True)
        print(f"Step 8c, mode: {_set_mode(tmp)}.", flush=True)
        app_id, first_line = _check_file(tmp, bundle)
        print(
            f"Step 8d, check: decrypting {tmp} gives back exactly what went in: "
            f"App ID {app_id}, and a key whose first line is {first_line}.",
            flush=True,
        )
        if os.path.lexists(out):
            raise Refused("rename", f"{out} appeared while this ran; nothing was overwritten")
        try:
            os.rename(tmp, out)
        except OSError as e:
            raise Refused("rename", f"{tmp} could not be renamed to {out} ({e.strerror or type(e).__name__})") from e
        stored = True
        print(f"Step 8e, rename: {tmp} is now {out}.")
        return app_id, first_line
    finally:
        if not stored and os.path.lexists(tmp):
            try:
                tmp.unlink()
                print(f"Removed {tmp}, which held only ciphertext.")
            except OSError as e:
                print(f"Could not remove {tmp} ({e.strerror or type(e).__name__}); it holds only ciphertext: remove it yourself.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Store the pr-sentinel App's private key encrypted with gpg, after GitHub accepts it, "
            "then remove the downloaded key file (#4784). Dry run unless --apply. The operator "
            "runs it in his own terminal; an agent never does."
        )
    )
    parser.add_argument(
        "--pem", required=True,
        help="absolute path of the private key file downloaded from the App's settings page",
    )
    parser.add_argument(
        "--out", default=str(_pat_session.DEFAULT_PR_SENTINEL_APP_PATH),
        help="where the encrypted file goes (default: %(default)s); never overwritten",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="encrypt, check, and remove the key file (the operator only)",
    )
    args = parser.parse_args(argv)

    try:
        print(f"Step 1, user: {_check_user()}.")
        app_id = _app_id()
        print(f"Step 2, App ID: {app_id}, from config/fleet-ids.json (pr_sentinel_app_id).")
        pem_path, pem, bits = _read_pem(args.pem)
        print(f"Step 3, --pem: {pem_path} is a regular file holding one RSA private key of {bits} bits.")
        out, tmp, folder = _check_out(args.out)
        print(f"Step 4, --out: nothing is at {out} or {tmp}, and {folder}.")
        print(f"Step 5, GitHub: {_prove_with_github(app_id, pem)}.")
    except Refused as r:
        return _fail(r.step, r.reason)

    print(
        f"Step 6, plan: encrypt App ID {app_id} and the key with gpg into {tmp} "
        "(gpg asks for a new passphrase), set it to mode 600, decrypt it to check it "
        f"(the passphrase is asked again), rename it to {out}, then remove {pem_path}."
    )

    if not args.apply:
        this = Path(__file__).resolve()
        command = (
            f"poetry -C {shlex.quote(str(this.parents[1]))} run python {shlex.quote(str(this))} "
            f"--pem {shlex.quote(str(pem_path))}"
        )
        if out != Path(_pat_session.DEFAULT_PR_SENTINEL_APP_PATH):
            command += f" --out {shlex.quote(str(out))}"
        print(f"Step 7, dry run: to store the key, the operator runs, in bash: {command} --apply")
        print("OK: dry run, nothing changed")
        return 0

    print("Step 7, apply: --apply was given; storing the key.")
    bundle = f"{app_id}\n{pem}"
    del pem
    try:
        _store(bundle, out, tmp)
    except Refused as r:
        return _fail(r.step, r.reason)
    finally:
        del bundle

    try:
        pem_path.unlink()
    except OSError as e:
        return _fail(
            "remove the key file",
            f"{pem_path} could not be removed ({e.strerror or type(e).__name__}). The key is stored "
            f"and checked at {out}; remove the key file yourself: rm {shlex.quote(str(pem_path))}",
        )
    if os.path.lexists(pem_path):
        return _fail(
            "remove the key file",
            f"{pem_path} is still there after removing it. The key is stored and checked at {out}",
        )
    print(f"Step 8f, remove: {pem_path} is removed, and nothing is at that path now.")

    print("Step 9, by hand: the key passed through places this program cannot reach.")
    print("  - Your browser's download history still lists the .pem file: delete that entry.")
    print("  - If a copy of the key ever went to the Windows Recycle Bin, delete it from there.")
    print("  - Any other copy of this key (another folder, the other side's disk) is still plaintext: remove it.")
    print(f"OK: the pr-sentinel App key is stored encrypted at {out}, and {pem_path} is removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
