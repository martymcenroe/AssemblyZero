# Standard 0022: Rendering and Reading PDFs (Agent-Portable)

**Status:** Approved
**Issue:** #1749
**Date:** 2026-07-12

## Problem

Agents routinely need to **read** a PDF a human saved — settings pages, vendor docs,
figures, forms. The Claude Code `Read` tool's built-in PDF page rendering shells out
to `pdftoppm` (poppler-utils), which is **not installed on the fleet's Windows boxes**.
When it's missing, `Read` on a PDF fails with `pdftoppm is not installed`, and the
agent is wrongly tempted to conclude it "can't render PDFs."

It can. This standard is the portable method, verified 2026-07-12 (rendered a 12-page
PDF to PNG and extracted its text with zero system dependencies).

## Method: PyMuPDF (`fitz`) — no system dependency

PyMuPDF bundles the MuPDF engine, so it renders and extracts **without poppler or any
system binary**. It is already a fleet dependency — IEEE-IC25-004 uses it in
`tools/census_v3.py`, `tools/map_v3.py`, and `tools/audit_affiliation_italics_v2.py`.

Two operations cover every agent need.

**1. Read a PDF as text** — fast and cheap; use when you need the words:

```python
import fitz  # PyMuPDF
doc = fitz.open(path)
text = "\n".join(doc[i].get_text() for i in range(doc.page_count))
```

**2. Render pages to PNG** — when layout, figures, or the visual matter; then `Read`
the PNGs as images (image reading needs no poppler):

```python
import fitz
doc = fitz.open(path)
for i, page in enumerate(doc):
    page.get_pixmap(dpi=150).save(f"{out}/page-{i + 1:03d}.png")
```

### Canonical helper

Drop this into a repo's `tools/pdf_render.py`, or run it from any poetry env that has
`pymupdf`:

```python
"""Render a PDF to PNGs and dump text — PyMuPDF only, no system poppler needed.

Usage: python pdf_render.py <pdf> [outdir] [dpi]
"""
import os
import sys
import fitz  # PyMuPDF

pdf = sys.argv[1]
outdir = sys.argv[2] if len(sys.argv) > 2 else "."
dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 150

os.makedirs(outdir, exist_ok=True)
doc = fitz.open(pdf)
base = os.path.splitext(os.path.basename(pdf))[0]
print(f"pages={doc.page_count} dpi={dpi}")

for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=dpi)
    out = os.path.join(outdir, f"{base}-p{i + 1:03d}.png")
    pix.save(out)
    print(f"wrote {out} ({pix.width}x{pix.height})")

print("--- page 1 text (first 400 chars) ---")
print(doc[0].get_text()[:400])
```

Run it (add `pymupdf` to the repo, or borrow a sibling env that already has it):

```bash
poetry add pymupdf                                       # once, per repo that needs it
poetry run python tools/pdf_render.py "C:/path/file.pdf" out/ 150
```

## Gotchas (earned 2026-07-12)

1. **Poppler is not on the Windows boxes.** `pdftoppm` / `pdftocairo` are absent, so
   both `pdf2image` (`convert_from_path`) and the `Read` tool's built-in PDF path fail.
   PyMuPDF and `pypdfium2` bundle their own engine and DO work — prefer PyMuPDF.
2. **Windows path form.** These render via *Windows* Python (poetry), not MSYS. Pass a
   drive-letter path (`C:/Users/…` or `C:\Users\…`), NOT the Bash `/c/Users/…` form —
   `fitz.open("/c/…")` raises `FileNotFoundError`. Forward slashes with a drive letter
   are fine.
3. **DPI.** 150 dpi reads cleanly and is cheap. Use 300 for high-fidelity figure export
   — thin lines vanish below that (IEEE re-renders figures at `dpi=300`).
4. **`pdf2image` needs poppler — don't use it for agent reads.** IEEE's
   `build_figures.py` uses it only because that machine has poppler; the portable
   choice is PyMuPDF.
5. **Run from an env that has `pymupdf`.** `poetry add pymupdf` to the working repo, or
   invoke a sibling env that already has it for one-offs.

## When to use which

| Need | Use |
|---|---|
| The words in the PDF | `doc[i].get_text()` |
| See layout / a figure / a rendered page | `get_pixmap(dpi=150).save(png)` → `Read` the PNG |
| High-fidelity figure export | `dpi=300` (or poppler `pdftoppm -r 300` where available) |

## Do NOT

- Do NOT conclude "I can't render PDFs" when `Read` fails with a poppler error — fall
  back to PyMuPDF.
- Do NOT reach for `pdf2image` / `convert_from_path` on a Windows box (no poppler).
- Do NOT pass MSYS `/c/…` paths to Windows Python.
