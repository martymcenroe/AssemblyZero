# 0902: What marks the Projects tree ReadOnly

**Date:** 2026-08-14
**Issue:** #2277 (split from #2136)
**Verdict:** Google Drive for Desktop. External to the pipeline, external to the fleet's tooling, and it stopped on 2026-08-01.

---

## The question

#2136 asked what in the pipeline applies the Windows ReadOnly attribute to worktree directories, and answered: nothing does. The attribute is ambient across the whole `Projects` tree, including repos that have never been rolled and caches like `.mypy_cache`. #2277 carried the remaining question: what applies it, then?

## The answer

**Google Drive for Desktop** (Drive File Stream 129.0.1.0, installed at `C:\Program Files\Google\Drive File Stream`) was backing up `C:\Users\mcwiz\Projects`. It marks the directories it manages. It stopped on **2026-08-01 at about 16:15**, and nothing created since carries the attribute.

No pipeline code, no fleet tool, and no scheduled task is involved. `schtasks /query /v` matches `Projects` zero times.

## The measurements

**1. It is specific to this tree.** If directories everywhere carried the attribute there would be no mystery to solve.

| Root | Marked |
|---|---|
| `C:\Windows` | 2/25 |
| `C:\Program Files` | 0/25 |
| `C:\Program Files (x86)` | 1/25 |
| **combined baseline** | **3/75 (4%)** |
| `Projects` | 110/118 (93%) |
| `Projects\AssemblyZero` | 24/24 (100%) |

**2. Directories only — not one file.**

| Repo | Directories | Files |
|---|---|---|
| AssemblyZero | 24/24 | 0/30 |
| boostgauge | 13/13 | 0/9 |
| Aletheia | 32/32 | 0/40 |
| Talos | 18/18 | 0/12 |

87 of 87 directories, 0 of 91 files. A backup or antivirus product rewriting attributes would generally touch both. A sync client marking the folders it manages would not.

**3. No `desktop.ini` anywhere.** 0 of 87 marked directories contains one, so this is not the Windows shell's folder-customisation mechanism, which is the usual innocent explanation for a ReadOnly folder.

**4. Freshly created directories are unmarked** — including nested ones, created seconds before measuring. Whatever does this walks existing trees rather than marking at creation.

**5. The boundary dates the last pass.** In `AssemblyZero/data`, sorted by creation time:

```
newest MARKED created:   2026-07-31 08:23:13  scratch-2026-07-31-claudemd-handoff
oldest UNMARKED created: 2026-08-02 01:43:55  worktrees
```

Everything older is marked; everything newer is not. All 33 scratch directories created since 2026-08-02 are unmarked.

**6. Drive's staging directories sit in the Projects root and fall idle inside that window.**

```
.tmp.driveupload     created 2026-07-18 19:19:14   last active 2026-08-01 16:15:03
.tmp.drivedownload   created 2026-08-01 12:32:42   last active 2026-08-01 16:01:18
```

`.tmp.driveupload` and `.tmp.drivedownload` are Google Drive for Desktop's staging directories, created in any folder it backs up. Their last activity — 2026-08-01 16:15 — sits between the last marked directory (07-31 08:23) and the first unmarked one (08-02 01:43).

Drive was not running when this was measured.

## Why it costs nothing

Measured directly: a file was created inside a marked directory, read back, and deleted. All three succeeded.

On Windows the ReadOnly flag on a **directory** is a shell hint, not a permission — unlike on a file, where it does block writes. This is why #2135's fix (clear the attribute, retry the plain `git worktree remove`) is the right one and why identifying the setter changes no code.

## Corroboration

The root `CLAUDE.md` carries an unrelated lesson earned 2026-07-24: an agent recursively walked a Google Drive `Other computers\<machine>` backup tree and forced ~70 GB of hydration. That incident is independent evidence that this machine was configured to back folders up to Drive, which is the configuration this audit found the traces of.

## The detection check

`tools/readonly_attribute_audit.py` re-runs all of it: the baseline comparison, the directory-versus-file split, the staging-directory check, and the boundary. It exits 1 if a directory created after the recorded last pass is marked, which is what "Drive backup was switched back on" would look like.

It is read-only. Nothing here is worth a destructive fix.

```
poetry run python tools/readonly_attribute_audit.py
```

## Left open

`.tmp.driveupload` holds **1.7 GB across 8,610 entries**, abandoned since 2026-08-01. Removing it is disk cleanup and an irreversible operator decision rather than a finding, so it is tracked separately in #2379 — including the step this audit did not take: confirming Drive is no longer configured for this folder before anything is deleted.
