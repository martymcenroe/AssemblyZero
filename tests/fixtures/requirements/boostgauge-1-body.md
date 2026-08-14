## Summary

Build the core gauge renderer for v1. This is Phase 4 of the on-camera speedrun arc (`#7 → #1 → #4 → #2 → #5` per `docs/speedrun/0002-route-v2.md`) and the foundation every other visual feature sits on.

## What this issue ships

A renderer function that takes a metric value (0–100) plus telltale peak values (from #41) and produces a `PIL.Image` of the v1 gauge. The image matches the written specification in `docs/design/0002-aesthetic-v1-stingray.md` — the canonical photograph there is inspiration only, never a comparator (ruling #262).

The renderer is callable as `render(value, telltales, size, config) → PIL.Image` per #45's skin protocol sketch. v1 ships only one skin (Stingray) but the renderer is structured skin-shaped from day one so #45 can add more without rewriting.

## Visual specification

**See `docs/design/0002-aesthetic-v1-stingray.md` — that doc is binding.** No re-specification here. Brief summary for orientation:

- Square chromed-metal housing, round matte-black dial inside.
- White Eurostile-adjacent numerals 0–100.
- Bold white tick marks (11 major, 4 minor between each).
- Luminescent candy-apple-red main needle with counterweight.
- Brick-red redline ring band occupying the outer 80–100% of dial radius, spanning values 60–100 (a rim band, never a pie segment; the two reds are deliberately distinct hues — rulings #228/#229, 2026-08-09).
- "BOOSTGAUGE" wordmark in white small caps below the pivot.
- Telltale needles (per #2) consume #41's `Telltale` outputs; rendered translucent at baseline — fading from baseline at 3 scale units of the main needle to full opacity at 2 units, holding full opacity closer in; opacity is computed per needle from its distance and applied uniformly to the whole needle (rulings #232/#242/#245, doc §Telltale needles) — behind the main needle.

Any divergence from the aesthetic doc requires updating the doc first.

## Requirements

- The renderer shall produce a `PIL.Image` from `render(value, telltales, size, config)` as a pure function: no hidden state, no side effects, no `tkinter` import.
- The renderer shall produce byte-identical images for identical inputs.
- The renderer shall draw the main needle, and position every telltale needle, on the axis `angle(value) = 225° − 2.7° × value` (ruling #255's binding mapping: value 0 at 225°, value 50 at 90°, value 100 at −45°; a 270° clockwise sweep).
- The renderer shall draw the six static elements identically at every value.
- The renderer shall draw the redline band as a rim band at the outer 80–100% of dial radius, spanning values 60–100.
- The renderer shall compute each telltale needle's rendering from its own peak per the telltale-opacity table below, applying the resulting opacity uniformly to that whole needle.
- The renderer shall render at any square size from 128×128 up, defaulting to 256×256, aspect-locked.

Telltale opacity, one row per condition (`d` is the scale distance |peak − main needle value|; baseline is the doc's §Telltale needles translucency):

| ID | Peak state | `d` (scale units) | Rendered opacity |
|---|---|---|---|
| T1 | None | — | not rendered |
| T2 | present | d ≥ 3 | baseline translucency |
| T3 | present | 2 < d < 3 | linear between baseline and 100% |
| T4 | present | d ≤ 2 | 100% |

## Implementation notes

- **Option C renderer (per `docs/design/0001-test-strategy.md`):** the renderer produces a `PIL.Image`. The application calls it on each refresh and hands the image to a tkinter Canvas via `PhotoImage`. The Canvas is dumb — it just displays the result. The renderer never imports `tkinter`.
- **Anti-aliasing:** Pillow handles it (renderer draws on a PIL Image, optionally supersampled internally if needed for crispness). The "tkinter Canvas doesn't anti-alias" concerns from the original body are no longer relevant under Option C.
- **Sizing:** Default 256×256 px (matches the canonical reference image dimensions). Resizable with aspect lock. Minimum 128×128.
- **Skin-shape:** Stingray's render logic lives in a module (e.g., `src/boostgauge/skins/stingray.py`) implementing the protocol sketched in #45. Application code calls into the skin module, not into hard-coded drawing logic in `gauge.py`.

## Dependencies

- **`docs/design/0002-aesthetic-v1-stingray.md`** — the binding visual spec.
- **`docs/design/0001-test-strategy.md`** — the binding test approach (Option C, baseline image policy).
- **#41** — `Telltale` class. The renderer consumes `Telltale.current_peak()` values to position the four telltale needles. #41 should land before or alongside this issue.
- **#7** — config (v1 is one skin, but config plumbing for which skin to load lives here).
- **#45** — skins protocol sketch. v1 follows the structure so #45 can add additional skins without renderer rewrites.

## State Variables and Ownership

Per AssemblyZero ADR 0228: every claim about a variable's fate belongs to its one owning criteria group, named by criterion ID prefix; any other mention cites the owner.

| Variable | Extension | Owner |
|---|---|---|
| The output image as a value | the returned `PIL.Image` object: type, purity, determinism, and the absence of `tkinter` | F (the function-contract criteria) |
| Static-element pixels | the pixels of `housing`, `dial`, `ticks`, `numerals`, `band`, `wordmark` | S (the static-scenery criteria) |
| Main-needle axis and pixels | the `needle` element: its axis from the angle mapping and its `#F73923` pixels | M (the main-needle criteria) |
| Telltale-needle visibility and opacity | the four `telltale` needles: drawn or not, and at what opacity | T (the telltale table and criteria) |

- Boundary term: **static elements** are exactly `housing`, `dial`, `ticks`, `numerals`, `band` (the redline ring), and `wordmark` — six, per the aesthetic doc's sections.
- Boundary term: **scale unit** is one unit of dial value; a **scale distance** `d` is |telltale peak − main needle value|.
- Boundary term: **baseline translucency** is the doc §Telltale needles value; **full opacity** is 100%.
- Boundary term: **peak** is a telltale's held maximum on the 0–100 scale (#41's `Telltale.current_peak()`); **coincident** means its peak equals the main needle's value exactly (`d` = 0), and **non-coincident** means `d` > 0.

## Acceptance Criteria

- [ ] F1 — `render(value, telltales, size, config) → PIL.Image` callable as a pure function (no hidden state, no side effects, no `tkinter` imports).
- [ ] F2 — Needle positions are deterministic functions of value (and per-telltale of peak value); provided the inputs are identical, two calls produce byte-identical output.
- [ ] S1 — Static gauge image at value=0, all telltales=None renders every element the aesthetic doc's text specifies, verified by doc-text-derived checks (housing and dial present; ticks and numerals per §layout; brick-red band at the ruled radii spanning 60–100; candy-apple needle on the ruled 225° rest axis; wordmark below the pivot) — and pinned thereafter by a SELF-generated visual-regression baseline accepted via the explicit `--generate-baselines` flow (test strategy 0001 §3). The canonical photograph is inspiration only and is never compared against (ruling #262).
- [ ] S2 — Image at value=100 with no telltales: every static element (housing, dial face, ticks, numerals, redline band, wordmark) renders identically to the value=0 image; per ruling #253 the two images may differ only where the main needle is drawn in either image. Where the needle points is M's.
- [ ] M1 — The main needle renders on the axis `angle(value) = 225° − 2.7° × value`: at value=0 the 225° rest axis, at value=100 the −45° rightmost axis, and every render-tier position test computes its expected axis from this mapping.
- [ ] M2 — Image at value=75: the main needle's tip lies inside the redline band; tip pixels (candy-apple `#F73923`) and band pixels (brick `#9B3020`) are distinct hues, verified by the render-tier test sampling both along the needle axis within the band.
- [ ] T1 — A telltale whose peak is None is not rendered (post-reset hides the needle).
- [ ] T2 — A telltale at scale distance d ≥ 3 renders at baseline translucency (the far case: value=70, peak=30 samples at the translucent blend).
- [ ] T3 — A telltale at 2 < d < 3 renders strictly between baseline and full opacity, at the linear midpoint within the visual-regression tolerance for d=2.5 (the mid-fade case: value=70, peak=72.5; ruling #246 — the case that distinguishes the fade from an on/off step).
- [ ] T4 — A telltale at d ≤ 2 renders at full opacity, applied uniformly to the whole needle — its protruding edge samples at full opacity (the near-overlap case: value=70, peak=72; rulings #242/#245).
- [ ] T5 — Image with all four telltales at varying NON-COINCIDENT peak values: four secondary needles visible at their angles, colors/widths/translucency per aesthetic doc §Telltale needles. Z-order is a spec convention, not a tested criterion (ruling #232). Full occlusion at exact coincidence is correct by design — at that instant the main needle itself displays the peak.
- [ ] V1 — Render-tier tests (per `tests/visual/` + strategy 0001) cover: value=0, value=50 (below the redline), value=75 (tip-in-band distinctness), value=80 (mid-arc), value=100, telltale combinations, the T2/T3/T4 distance cases above, and post-reset (T1).

## Out of scope

- Animation / damping curves between values (defer to a follow-on issue).
- Right-click reset interaction (#2 territory).
- Multi-skin support (#45 territory; v1 ships only Stingray).
- Digital readout below the pivot (not in the canonical image; not in the v1 aesthetic).

## Revision history

| Date | Change | Why |
|---|---|---|
| 2026-08-09 | Redline codified as brick-red ring band at outer 80–100% of radius; needle as candy-apple red; value=75 criterion made testable (tip-vs-band pixel sampling); render-tier list gains 75 (in-band) and 80 (mid-arc), 50 relabeled below-the-redline. | Rulings on #228 (the planned tests could not detect a same-red needle inside the band; the doc even mandated matching reds) and #229 (value 50 cannot be "mid-arc" when the arc starts at 60). Both conflicts were detected by the pipeline's requirements gate on 2026-08-09's roll. |
| 2026-08-09 | Telltale criterion made testable: proximity-opacity ramp (100% within 3 scale units of the main needle), coincidence occlusion accepted by design, z-order demoted to spec convention; render-tier list gains the near-overlap and far telltale cases. | Ruling on #232 — the gate caught that z-order had no pixel consequence without overlap and contradicted visibility with it. |
| 2026-08-10 | The visual-summary telltale line qualified: translucent is the baseline, and the #232 proximity ramp (full opacity within 3 scale units of the main needle) is the governing exception near the needle. | Ruling on #238 — the unqualified "rendered translucent" survived the 2026-08-09 #232 edit and contradicted the near-overlap render-tier case (value=70, peak at 72). The aesthetic doc already carried both rules; only this summary line lagged. |
| 2026-08-10 | Proximity ramp's completion point specified: opacity fades from baseline at 3 scale units to 100% at 2 units and holds 100% anywhere closer (aesthetic doc updated via PR #243; summary line aligned). The near-overlap test case (value=70, peak at 72 → 100%) is now exact. | Ruling on #242 — "ramping to full opacity" left the completion point unstated; a ramp completing only at coincidence never shows full opacity anywhere visible (coincidence is occluded by design), contradicting the near-overlap test case that samples 100% at 2 units. |
| 2026-08-10 | AC-2 rewritten: the canonical photograph is inspiration, never a comparator. The value=0 render is verified by doc-text-derived element checks and pinned by a SELF-generated baseline (`--generate-baselines`, strategy 0001 §3). #230 (image regen) superseded and closed. | Operator ruling #262 (aesthetic doc updated via PR #263) — the spec reviewer refused six runs in a row to write the photo-comparison test, because the photo shows retired colors and regenerating an AI photograph to spec is not an achievable task. The picture is not the requirement; the text is. |
| 2026-08-10 | Opacity declared per-needle: one value computed from the needle's scale distance to the main needle, applied uniformly to every pixel of that needle (aesthetic doc updated via PR #250; summary line aligned). | Ruling on #245 — a strict per-pixel reading would render a boundary needle's protruding tip dimmer than its base, while the near-overlap test case requires the protruding edge to sample at full opacity. One needle, one opacity. |
| 2026-08-10 | Render-tier list gains the mid-fade case: value=70 with a peak at 72.5 samples strictly between baseline and full opacity, at the linear midpoint within tolerance. | Ruling on #246 — the existing cases sampled only the fade band's endpoints (2 units → full, far → baseline), so an on/off step implementation would pass every planned test; the fade was untestable as written. |
| 2026-08-10 | The value=100 criterion rephrased: "rest of the gauge unchanged from value=0" became "every static element renders identically to value=0; the two images may differ only where the main needle is drawn in either image." | Ruling on #253 — the spec-stage review caught that the literal reading is unsatisfiable: moving the needle to 100 necessarily changes the pixels it occupied at 0 (needle → background), so "unchanged from value=0" could never hold pixel-for-pixel. The criterion meant the static scenery, and now says so. |
| 2026-08-14 | Full ADR 0226 + ADR 0228 conversion: a `## Requirements` section (R1–R7, EARS form) importing the binding numbers (the #255 angle mapping, the ramp thresholds, the band geometry); the telltale-opacity decision table (T1–T4, one row per condition); a State Variables and Ownership section (four variables, single tagged owners F/S/M/T, three boundary terms); every acceptance criterion carrying its group ID, with the telltale render-tier cases graduated into per-row criteria T1–T4 and the two red RGBs imported into M2 per the values-not-pointers principle. No requirement's meaning changed — every sentence traces to an existing ruling or the binding doc. | The #7 precedent: eighteen conflicts across twelve halts were what unconverted prose cost that issue. Converting before the roll, checker-clean from the first draft, is the lesson applied. |
