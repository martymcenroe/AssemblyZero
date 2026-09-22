#!/usr/bin/env python3
"""One-shot: fix the workflow concurrency syntax error on AssemblyZero (Closes #3422).

Uses in-process classic PAT (ADR-0216) to bootstrap past branch protection
and update the workflow files via the Contents API.
"""

import base64
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session
import deploy_auto_reviewer_workflow as deploy_mod

GH_API = "https://api.github.com"
GITHUB_USER = "martymcenroe"
REPO = "AssemblyZero"

FILES_TO_PATCH = [
    ".github/workflows/auto-reviewer-caller.yml",
    ".github/workflows/auto-reviewer.yml"
]

BRANCHES_TO_FIX = [
    "main",
    "adr/fully-landed",
    "tools/audit-fully-landed"
]

def remove_concurrency_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    skip = 0
    for line in lines:
        if skip > 0:
            skip -= 1
            continue
        if line.startswith("concurrency:"):
            skip = 2
            continue
        out.append(line)
    return "".join(out)

def do_put_workflow(repo: str, branch: str, pat: str) -> tuple[bool, str | None]:
    headers = deploy_mod._headers(pat)
    
    for path in FILES_TO_PATCH:
        print(f"  Fetching {path} on {branch}...")
        r = requests.get(f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{path}?ref={branch}", headers=headers)
        if r.status_code == 404:
            continue
        if r.status_code >= 300:
            return False, f"Failed to get {path}: {r.status_code}"
            
        data = r.json()
        sha = data["sha"]
        content = base64.b64decode(data["content"]).decode("utf-8")
        
        new_content = remove_concurrency_block(content)
        if new_content == content:
            print(f"    No changes needed for {path}")
            continue
            
        print(f"  PUT {path}...")
        b64_new = base64.b64encode(new_content.replace('\r\n', '\n').encode("utf-8")).decode("ascii")
        payload = {
            "message": f"fix(ci): remove concurrency from {path} to fix workflow error",
            "content": b64_new,
            "branch": branch,
            "sha": sha
        }
        
        r = requests.put(f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{path}", json=payload, headers=headers)
        if r.status_code >= 300:
            return False, f"Failed to PUT {path}: {r.status_code} {r.text}"
        print(f"    succeeded.")
        
    return True, None

def my_put_workflow(repo: str, branch: str, existing_sha: str | None, pat: str) -> tuple[bool, str | None]:
    # We only patch 'main' via deploy_with_bootstrap.
    return do_put_workflow(repo, branch, pat)

def main():
    print("Fixing workflow concurrency syntax error on AssemblyZero branches...")
    
    # Monkey-patch the PUT function so deploy_with_bootstrap runs our logic
    deploy_mod.put_workflow = my_put_workflow
    
    with classic_pat_session(reason="remove concurrency from workflows to fix syntax error") as pat:
        print("\n--- Fixing main (protected) ---")
        ok, err, _ = deploy_mod.deploy_with_bootstrap(REPO, "main", pat)
        if not ok:
            print(f"FAILED on main: {err}")
            return 1
            
        for branch in BRANCHES_TO_FIX[1:]:
            print(f"\n--- Fixing {branch} ---")
            ok, err = do_put_workflow(REPO, branch, pat)
            if not ok:
                print(f"FAILED on {branch}: {err}")
                return 1
                
    print("\nAll branches updated! Auto Review should now pass.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
