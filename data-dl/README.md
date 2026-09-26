# data-dl/ -- downloaded material, never committed

Anything fetched from somewhere else lives here: papers, report drafts,
spreadsheets, exports, images, meeting recordings.

**This directory is gitignored.** Nothing in it is committed except this README and the empty substructure `.gitkeep` files.

Please organize your downloads into the appropriate subfolders:
- `audio/` (for .m4a, .mp3, etc.)
- `transcripts/` (for raw Whisper outputs)
- `reference/` (for heavy PDFs, spreadsheets, and reference materials)
That is deliberate -- downloaded material is usually bulk, usually binary, and
usually reproducible by downloading it again. Git is a poor store for it and the
cost is permanent, because every clone pays for it forever.

| Directory | Tracked? | Purpose |
| :--- | :--- | :--- |
| `data/` | No       | Ephemeral session artifacts, logs, unreviewed scratchpad state |
| `data-g/` | **Yes**  | Source-of-truth data, reference material, golden fixtures |
| `data-dl/`| No       | Downloaded and fetched material: papers, drafts, exports, recordings |

If something you downloaded genuinely needs to be durable -- it cannot be fetched
again, or the project depends on it as canonical input -- move it to `data-g/`
deliberately, rather than committing it from here. That move should be a decision
someone made, not a side effect of where a file happened to land.

(Convention established in AssemblyZero #2485, after `data-g/` spent months
absorbing downloads because this directory did not exist.)
