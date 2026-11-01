# Test Report: one file chooses each role's model (#4450)

`tests/unit/test_fleet_models.py` holds T1 to T6:

- T1: changing one word in a fixture copy changes the model a role gets, and going back to Codex is the two words the file names.
- T2: a retired model raises through an `except Exception`, naming the role and the model.
- T3: an unknown role, a missing file, a broken file, a forbidden model and a role naming no defined model each stop the run.
- T4: `--check` exits 1 and names the role, and exits 0 when every role has a live model.
- T5: `REVIEWER_MODEL`, `FORBIDDEN_MODELS` and the default profile's seats read the switch.
- T6: the real file defines every model each role names, every provider is on the closed list, and the file says how to go back to Codex.

`tests/unit` against the worktree, 2026-10-31: 13,342 passed, 66 skipped, 7 deselected, 7 xfailed, none failed, in 12 minutes 27 seconds.

`python assemblyzero/fleet_models.py --check` on the real file prints 17 role lines and exits 1 for the two roles on the retired Codex model, as intended.
