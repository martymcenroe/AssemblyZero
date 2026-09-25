# Implementation Report — Every shutil.rmtree is a move-aside or asserts ownership (#3518, #3231, #3528)

Backfilled 2026-09-25 after the merge, from PR #3539 (merge `c8e350a1`) and its body (#3559). The PR closed #3518, #3231 and #3528; this directory sits under the branch's leading issue. No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502.

## What was wrong

The shell guard denies `rm -rf` to the agent. `shutil.rmtree` is the same operation, and nothing saw it. An `ast` walk of `assemblyzero/` and `tools/` found 10 call sites, not the 6 the issue listed. The three worst: `create_worktree` rmtree'd `../{Repo}-{issue}` during an ordinary unattended run whenever the directory had no `.git` (#3231); `tools/speedrun_reset.py` deleted any clean but unregistered `{Repo}-{issue}` directory; `tools/archive_worktree_lineage.py` accepted a main checkout and, pointed at one, emptied `__pycache__` and would have run `poetry env remove --all` there (#3528).

## What changed

Moved aside instead of deleted, each rename stamped and printed: `create_worktree` (`<name>.bak-<stamp>`), `speedrun_reset._remove_worktree_at` (same), `audit.shift_lineage_versions` (the oldest `-lld-n2` generation goes to `docs/lineage/discarded/`), `archive_worktree_lineage.archive_lineage` (a previous archive to `<dest>.prev-<stamp>`).

Ownership asserted before the delete, seven sites at the time: `archive_worktree_lineage.clean_ephemeral` and `evict_poetry_venv` and the tool's `main()` refuse unless `--worktree` is a linked worktree (#3528); `dependabot_review._remove_node_modules` refuses outside a linked worktree; `speedrun/archive._rmtree` refuses any directory that is not an archive this module wrote; `verify_phases._hill_climb`, `visual_gate.render_round` and `speedrun_reset`'s post-copy removal assert their own target; `adversarial_writer` stages inside its output directory rather than the OS temp directory, so its move is a rename on one filesystem.

(`clean_ephemeral` was later removed outright by #3558, taking the site count to six.)

## Files

`assemblyzero/speedrun/archive.py`, `assemblyzero/visual_gate/gate.py`, `assemblyzero/workflows/requirements/audit.py`, `assemblyzero/workflows/testing/nodes/adversarial_writer.py`, `assemblyzero/workflows/testing/nodes/verify_phases.py`, `tools/archive_worktree_lineage.py`, `tools/dependabot_review.py`, `tools/run_implement_from_lld.py`, `tools/speedrun_reset.py`, and four test files.
