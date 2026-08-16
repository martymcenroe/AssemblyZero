"""Land the windows-latest CI job via the Contents API (#2431).

A fine-grained PAT cannot push a workflow file:

    ! [remote rejected] refusing to allow a Personal Access Token to create or
      update workflow `.github/workflows/ci.yml` without `workflow` scope

So this edit goes through the GitHub Contents API with the in-process classic
PAT, per ADR 0216. Widening the fine-grained PAT is not the alternative -- an
agent must not broaden its own guardrails.

THE OPERATOR RUNS THIS, NOT AN AGENT. When an agent invokes it through its own
Bash tool the Python process is the agent's child, and ADR 0216's "the PAT
lives only in the Python heap" guarantee assumes the process is the operator's.

    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_windows_ci_job.py --apply

Without --apply it prints the change and exits, touching nothing.

## What it adds and why

CI runs `ubuntu-latest`; the fleet runs Windows. Everything Windows-only in the
emergency stop -- the taskkill tree, tasklist pid identification, the kill-file
watch against a real child -- is therefore verified by nobody. The asymmetry
has already bitten in the other direction: #2422's POSIX tree-kill SIGKILLed
its own caller, and only the Linux job caught it.

The job is deliberately NOT the whole suite on a second OS, which would double
CI for coverage the ubuntu job already provides. It selects `-m windows_paths`,
which runs in seconds, and runs `--collect-only` first so a marker that stops
matching fails loudly instead of passing by selecting nothing.
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GH_API = "https://api.github.com"
OWNER = "martymcenroe"
REPO = "AssemblyZero"
WORKFLOW_PATH = ".github/workflows/ci.yml"
BRANCH = "2431-windows-ci-job"
ISSUE = 2431

#: Appended to ci.yml. Kept as one block so the diff is reviewable in the PR.
JOB_YAML = """
  # The fleet runs Windows; the job above runs ubuntu. Everything Windows-only
  # -- the emergency stop's taskkill tree, tasklist pid identification, the
  # kill-file watch against a real child -- was therefore verified by nobody
  # (#2431). That asymmetry has already bitten in the other direction: #2422's
  # POSIX tree-kill SIGKILLed its own caller, and only the Linux job found it.
  #
  # Deliberately NOT the whole suite on a second OS. That would double CI for
  # coverage the ubuntu job already provides; this selects the marked subset,
  # which runs in seconds.
  windows-paths:
    runs-on: windows-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v7

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          virtualenvs-create: true
          virtualenvs-in-project: true

      - name: Install dependencies
        run: poetry install --no-interaction --with dev

      # A marker that stops matching would make this job pass by selecting
      # nothing, which is the "verified by nobody" state wearing a green tick.
      - name: Fail if the marked set is empty
        run: poetry run pytest tests/unit/ -m windows_paths --collect-only -q
        env:
          LANGSMITH_TRACING: "false"

      - name: Run the Windows-only paths
        run: poetry run pytest tests/unit/ -m windows_paths -v --tb=short
        env:
          LANGSMITH_TRACING: "false"
"""

#: Added to the guard file once the job exists. Asserting these before the job
#: lands would be a test written to fail.
GUARD_TESTS = '''

class TestTheCiJobExists:
    """These land WITH the workflow job (#2431). Asserting them before it
    exists would be a test written to fail, so they arrive together."""

    def _ci(self) -> str:
        return (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

    def test_there_is_a_windows_job(self):
        assert "windows-latest" in self._ci()

    def test_it_selects_this_marker(self):
        assert f"-m {MARKER}" in self._ci()

    def test_it_guards_against_an_empty_selection(self):
        """A --collect-only step first, so an empty set fails loudly instead
        of passing silently."""
        assert "--collect-only" in self._ci()
'''

GUARD_PATH = "tests/unit/test_windows_paths_marker.py"


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_file(pat: str, path: str, ref: str) -> tuple[str, str]:
    """(decoded text, blob sha) for a file at a ref."""
    response = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{path}",
        headers=_headers(pat), params={"ref": ref}, timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    text = base64.b64decode(payload["content"]).decode("utf-8")
    return text, payload["sha"]


def _put_file(pat: str, path: str, text: str, sha: str, message: str) -> None:
    # CRLF normalization is load-bearing on Windows: the Contents API stores
    # bytes verbatim, so submitting a CRLF body flips the whole file's line
    # endings on origin and makes a one-job change look like a rewrite.
    body = text.replace("\r\n", "\n").encode("utf-8")
    response = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{path}",
        headers=_headers(pat),
        json={
            "message": message,
            "content": base64.b64encode(body).decode("ascii"),
            "sha": sha,
            "branch": BRANCH,
        },
        timeout=30,
    )
    response.raise_for_status()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="actually create the branch, commit and PR (default: dry run)",
    )
    args = parser.parse_args(argv)

    if not args.apply:
        print("DRY RUN -- nothing will be changed. Re-run with --apply.\n")
        print(f"Would append this job to {WORKFLOW_PATH}:")
        print(JOB_YAML)
        print(f"Would append the ci.yml guards to {GUARD_PATH}.")
        print(f"Would open a PR closing #{ISSUE}.")
        return 0

    reason = f"land the windows-latest CI job in {OWNER}/{REPO} (#{ISSUE})"
    with classic_pat_session(reason=reason) as pat:
        head = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/git/ref/heads/main",
            headers=_headers(pat), timeout=30,
        )
        head.raise_for_status()
        base_sha = head.json()["object"]["sha"]

        ref = requests.post(
            f"{GH_API}/repos/{OWNER}/{REPO}/git/refs",
            headers=_headers(pat),
            json={"ref": f"refs/heads/{BRANCH}", "sha": base_sha},
            timeout=30,
        )
        if ref.status_code not in (201, 422):  # 422 == already exists
            ref.raise_for_status()

        ci_text, ci_sha = _get_file(pat, WORKFLOW_PATH, BRANCH)
        if "windows-latest" in ci_text:
            print("The windows job is already present; nothing to do.")
        else:
            _put_file(
                pat, WORKFLOW_PATH, ci_text.rstrip("\n") + "\n" + JOB_YAML,
                ci_sha,
                f"ci: run the Windows-only stop paths on windows-latest "
                f"(Closes #{ISSUE})",
            )
            print(f"Appended the job to {WORKFLOW_PATH}.")

        guard_text, guard_sha = _get_file(pat, GUARD_PATH, BRANCH)
        if "TestTheCiJobExists" in guard_text:
            print("The ci.yml guards are already present; nothing to do.")
        else:
            _put_file(
                pat, GUARD_PATH, guard_text.rstrip("\n") + "\n" + GUARD_TESTS,
                guard_sha,
                f"test: assert the windows CI job stays wired (Closes #{ISSUE})",
            )
            print(f"Appended the ci.yml guards to {GUARD_PATH}.")

        body = (
            f"Closes #{ISSUE}\n\n"
            "CI runs `ubuntu-latest`; the fleet runs Windows. Everything "
            "Windows-only in the emergency stop -- the `taskkill` tree, "
            "`tasklist` pid identification, the kill-file watch against a real "
            "child -- was verified by nobody.\n\n"
            "The tests themselves landed in #2451, proven on Windows: 11 "
            "passing in 15 seconds, including the kill-file path with the "
            "launcher mid-call driving the real `roll_issue`. This adds the "
            "job that runs them without a human choosing to.\n\n"
            "Deliberately not the whole suite on a second OS -- that would "
            "double CI for coverage the ubuntu job already provides. It "
            "selects `-m windows_paths`, and runs `--collect-only` first so a "
            "marker that stops matching fails loudly rather than passing by "
            "selecting nothing.\n\n"
            "Landed by the Contents API because a fine-grained PAT cannot push "
            "a workflow file (ADR 0216).\n"
        )
        pull = requests.post(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
            headers=_headers(pat),
            json={
                "title": (
                    "ci: run the Windows-only stop paths on windows-latest "
                    f"(Closes #{ISSUE})"
                ),
                "head": BRANCH,
                "base": "main",
                "body": body,
            },
            timeout=30,
        )
        if pull.status_code == 201:
            print(f"PR opened: {pull.json()['html_url']}")
        else:
            print(f"PR not created ({pull.status_code}): {pull.text[:400]}")
            existing = requests.get(
                f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
                headers=_headers(pat), params={"head": f"{OWNER}:{BRANCH}"},
                timeout=30,
            )
            if existing.ok and existing.json():
                print(f"Existing PR: {existing.json()[0]['html_url']}")

    print(
        "\nThe PR is open. Let CI and Cerberus finish, then merge it as usual.\n"
        "The windows-paths job will not appear on THIS PR -- a workflow added "
        "in a PR\nfirst runs on the branch it lands on."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
