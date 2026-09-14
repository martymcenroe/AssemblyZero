import os
import subprocess
import json
import time

projects_dir = "/mnt/c/Users/mcwiz/Projects"

print(f"# Fully Landed Audit Report\n\nGenerated for `{projects_dir}`.\n")

dirs = [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))]
dirs.sort()

repos = []
worktrees = []
unknown = []

for d in dirs:
    path = os.path.join(projects_dir, d)
    if os.path.isdir(os.path.join(path, ".git")):
        repos.append(d)
    elif os.path.isfile(os.path.join(path, ".git")):
        worktrees.append(d)
    else:
        unknown.append(d)

print("## Executive Summary")
print(f"- Total Main Repositories: {len(repos)}")
print(f"- Orphaned / Active Worktree Directories: {len(worktrees)}")
print(f"- Unknown / Non-Git Directories: {len(unknown)}")
print("\n---\n")

print("## Repository Audit\n")

def run_cmd(cmd, cwd):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(cmd, cwd=cwd, env=env, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1

for repo in repos:
    print(f"### {repo}")
    repo_path = os.path.join(projects_dir, repo)
    
    # THROTTLE: Be nice to local disk IO and GitHub API abuse limits
    time.sleep(2)
    
    # 1. Working Directory Clean
    status_out, _ = run_cmd("git status --porcelain", repo_path)
    clean = (len(status_out) == 0)
    
    # 2. No Dangling Worktrees
    wt_out, _ = run_cmd("git worktree list", repo_path)
    wt_lines = [line for line in wt_out.split('\n') if line.strip()]
    dangling_wts = len(wt_lines) > 1
    
    # 3. No Local Stashes
    stash_out, _ = run_cmd("git stash list", repo_path)
    stashes = [line for line in stash_out.split('\n') if line.strip()]
    has_stashes = len(stashes) > 0
    
    # THROTTLE
    time.sleep(2)
    
    # 4. No Open Pull Requests
    pr_out, pr_code = run_cmd("gh pr list --json number", repo_path)
    open_prs = 0
    if pr_code == 0 and pr_out:
        try:
            prs = json.loads(pr_out)
            open_prs = len(prs)
        except:
            open_prs = -1
    else:
        open_prs = -1

    # THROTTLE
    time.sleep(2)

    # 5. Main Branch Synced
    run_cmd("git fetch origin", repo_path)
    branch_out, _ = run_cmd("git branch --show-current", repo_path)
    if branch_out == "main":
        sync_out, _ = run_cmd("git status -sb", repo_path)
        synced = ("behind" not in sync_out and "ahead" not in sync_out)
    else:
        sync_out, sync_code = run_cmd("git rev-list --left-right --count main...origin/main", repo_path)
        if sync_code == 0 and sync_out:
            parts = sync_out.split()
            synced = (parts == ['0', '0'])
        else:
            synced = False
            
    is_fully_landed = clean and not dangling_wts and not has_stashes and open_prs == 0 and synced
    status_str = "✅ **FULLY LANDED**" if is_fully_landed else "❌ **ACTION REQUIRED**"
    print(status_str)
    
    print(f"- [x] Directory Clean" if clean else f"- [ ] Directory Clean (`{len(status_out.splitlines())}` files modified/untracked)")
    print(f"- [x] No Dangling Worktrees" if not dangling_wts else f"- [ ] No Dangling Worktrees (`{len(wt_lines)}` total worktrees found)")
    print(f"- [x] No Local Stashes" if not has_stashes else f"- [ ] No Local Stashes (`{len(stashes)}` stashes found)")
    
    if open_prs == -1:
        print("- [ ] No Open Pull Requests (Error querying `gh`)")
    else:
        print(f"- [x] No Open Pull Requests" if open_prs == 0 else f"- [ ] No Open Pull Requests (`{open_prs}` open PRs)")
        
    print(f"- [x] Main Branch Synced" if synced else "- [ ] Main Branch Synced (Ahead/Behind origin/main)")
    print()

print("## Worktree Directory Audit")
if not worktrees:
    print("No orphaned or active worktree directories found.")
else:
    for wt in worktrees:
        print(f"- `{wt}`")
