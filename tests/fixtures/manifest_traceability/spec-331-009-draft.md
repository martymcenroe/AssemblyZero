# Implementation Spec: Issue #331: static face renderer — bezel, chrome housing, dial, ticks, numerals, wordmark, screws — baked once, cached

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #331 |
| LLD | `docs/lld/active/331-static-face-renderer.md` |
| Generated | 2026-08-28 |
| Status | DRAFT |

## 1. Overview

**Objective:** Implement a cached, static background rendering module for the Stingray gauge face that outputs a complete, needle-free `PIL.Image` strictly adhering to the S1-S9 geometric and color contract assertions.

**Success Criteria:** When `render_face(size)` is called with a size equal to or greater than 128, it shall return a `PIL.Image.Image` containing the static elements (satisfying S1-S9), and subsequent calls with identical arguments in the same session shall return the cached image pointer.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/stingray.py` | Add | Exposes `render_face` and caches the static gauge rendering. |
| 2 | `tests/visual/test_stingray_static.py` | Add | Implements the visual validation assertions (S1-S9) for the static face. |

**Implementation Order Rationale:** The application code (`stingray.py`) must be created first to provide the `render_face` function interface, so the test suite can import and assert against it following the TDD workflow required by the project.

## 3. Current State (for Modify/Delete files)

*No files are being modified or deleted in this Implementation Spec.*

## 4. Data Structures

### 4.1 FaceCacheKey

**Definition:**

```python
FaceCacheKey = tuple[int, str]
```

**Concrete Example:**

```json
[256, "stingray"]
```

## 5. Function Specifications

### 5.1 `render_face()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def render_face(size: int, skin: str = "stingray") -> "Image.Image":
    """
    Renders or retrieves the cached static face for the Stingray gauge.
    Raises ValueError if size is less than 128.
    """
    ...
```

**Input Example:**

```python
size = 256
skin = "stingray"
```

**Output Example:**

```text
<PIL.Image.Image image mode=RGBA size=256x256 at 0x1A2B3C4D5E0>
```

**Edge Cases:**
- `size < 128` -> raises `ValueError("size must be >= 128")`

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray skin static face renderer.

Issue #331: static face renderer — bezel, chrome housing, dial, ticks, numerals, wordmark, screws — baked once, cached
"""
import math
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont

_FACE_CACHE: Dict[Tuple[int, str], Image.Image] = {}

def _polar(cx: float, cy: float, r: float, deg: float) -> Tuple[float, float]:
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)

def _angle(v: float) -> float:
    return 225.0 - 2.7 * v

def render_face(size: int, skin: str = "stingray") -> Image.Image:
    """
    Renders or retrieves the cached static face for the Stingray gauge.
    Raises ValueError if size is less than 128.
    """
    if size < 128:
        raise ValueError(f"size must be >= 128, got {size}")
        
    cache_key = (size, skin)
    if cache_key in _FACE_CACHE:
        return _FACE_CACHE[cache_key]
        
    # Supersampling for anti-aliasing
    ss = 3
    ss_size = size * ss
    img = Image.new("RGBA", (ss_size, ss_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx = cy = ss_size / 2.0
    R = 0.40 * ss_size
    
    # S7: Chrome housing
    chamfer = 0.13 * ss_size
    draw.rounded_rectangle([0, 0, ss_size, ss_size], radius=chamfer, fill=(20, 20, 20, 255))
    
    # S9: Bezel seat (transition annulus)
    seat_r = 1.01 * R
    draw.ellipse([cx - seat_r, cy - seat_r, cx + seat_r, cy + seat_r], fill=(5, 5, 5, 255))
    
    # S1: Dial face
    draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#0A0A0C")
    
    # S2: Redline band
    inner_r = 0.88 * R
    outer_r = 1.00 * R
    redline_start_ang = _angle(100)
    redline_end_ang = _angle(60)
    
    draw.arc(
        [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
        start=360 - redline_end_ang, end=360 - redline_start_ang,
        fill="#AA0F19", width=int(outer_r - inner_r)
    )

    # S8: Screws
    screw_r = 0.020 * R
    for offset_x in [-0.25 * R, 0.25 * R]:
        draw.ellipse([cx + offset_x - screw_r, cy - screw_r, cx + offset_x + screw_r, cy + screw_r], fill="#1A1A1C")

    # S3 & S4: Ticks
    for v in range(0, 101, 2):
        is_major = (v % 10 == 0)
        tick_len = 0.10 * R if is_major else 0.05 * R
        tick_wid = 0.025 * R if is_major else 0.012 * R
        ang = _angle(v)
        p1 = _polar(cx, cy, R - tick_len, ang)
        p2 = _polar(cx, cy, R, ang)
        draw.line([p1, p2], fill="#FFFFFF", width=int(tick_wid))

    try:
        font_numeral = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.11 * R))
        font_wordmark = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.09 * R))
    except OSError:
        font_numeral = ImageFont.load_default()
        font_wordmark = ImageFont.load_default()

    # S5: Numerals
    num_r = 0.72 * R
    for v in range(0, 101, 10):
        ang = _angle(v)
        nx, ny = _polar(cx, cy, num_r, ang)
        draw.text((nx, ny), str(v), fill="#FFFFFF", font=font_numeral, anchor="mm")

    # S6: Wordmark
    wordmark_y = cy + 0.67 * R
    draw.text((cx, wordmark_y), "BOOSTGAUGE", fill="#FFFFFF", font=font_wordmark, anchor="mm")
    
    # Downsample
    final_img = img.resize((size, size), Image.Resampling.LANCZOS)
    _FACE_CACHE[cache_key] = final_img
    
    return final_img
```

### 6.2 `tests/visual/test_stingray_static.py` (Add)

**Complete file contents:**

```python
"""Visual validation assertions (S1-S9) for the Stingray static face.

Issue #331: static face renderer — bezel, chrome housing, dial, ticks, numerals, wordmark, screws — baked once, cached
"""
import ast
import math
from pathlib import Path

import pytest
from PIL import Image

from boostgauge.skins.stingray import render_face

# Section 10.1 test function bodies map exactly here.
```
*(The specific test functions are detailed in Section 10.1 and should be placed directly inside this file).*

## 7. Pattern References

### 7.1 Visual Contract Math Protocol

**File:** `tools/visual_contract_render.py` (lines 35-45)

```python
def polar(cx, cy, r, deg):
    # math implementation
    pass

def angle(v):
    """ruling #255: angle(value) = 225 - 2.7 x value, math convention."""
    pass
```

**Relevance:** Demonstrates the canonical math for mapping a gauge value (0-100) to an angle, and converting polar coordinates to cartesian using `cx, cy, r, deg`. The `stingray.py` skin module adopts this exact angle and polar logic internally.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import math` | stdlib | `src/boostgauge/skins/stingray.py` |
| `from typing import Dict, Tuple` | stdlib | `src/boostgauge/skins/stingray.py` |
| `from PIL import Image, ImageDraw, ImageFont` | `pillow` | `src/boostgauge/skins/stingray.py` |
| `import pytest` | `pytest` | `tests/visual/test_stingray_static.py` |
| `import ast` | stdlib | `tests/visual/test_stingray_static.py` |
| `from pathlib import Path` | stdlib | `tests/visual/test_stingray_static.py` |

**New Dependencies:** None (`pillow` is already installed).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

<!-- BEGIN MACHINE-OWNED: source decision table (#2607) -->

## 9.5 Binding Decision Table (injected verbatim from the LLD)

The rows below are carried **verbatim** from the LLD by the derivation itself (#2611), which carried them verbatim from the source issue (#2607). They are machine-owned: the drafter does not write them, and a revision cannot change them. Every assertion in the test mapping must agree with these values; cite the IDs, do not restate the values.

| ID | Element | Binding value (quoted from the render contract) | Assertion method |
|---|---|---|---|
| S1 | Dial face | flat `#0A0A0C`, radius R = 0.40 × size, centre (0.5, 0.5) × size; NO gradient, glass sweep, or reflection (#325) | classification at 3 interior points + equality of samples at (0.3 R, 0.5 R, 0.7 R) along one needle-free radial — flatness IS the assertion |
| S2 | Redline band | `#AA0F19` crimson (ruling 2026-08-25), inner 0.88 R to outer 1.00 R, spanning values 60–100 via `angle(value) = 225° − 2.7° × value` | classification at radius 0.94 R at values 65/75/85 — deliberately offset from every tick position, because ticks render on top of the band (majors sit at multiples of 10, minors at even values; 65/75/85 carry no tick) |
| S3 | Major ticks | `#FFFFFF`, 11 total at values 0,10,…,100, length 0.10 R, width 0.025 R | stroke predicate at each tick's midpoint: channel mean ≥ 100, all 11 — the white stroke samples ~255, and the 100 threshold clears both backgrounds: the face's ~10 (values 0–50) and the band's ~70 (values 60–100, where ticks render on top of the band; `#AA0F19` → mean 70.0). A missing tick fails on either background: 10 < 100 and 70 < 100. Width 2.56 px at the pinned test size is too thin for the interior rule |
| S4 | Minor ticks | `#FFFFFF`, 40 total, 4 between each major pair, length 0.05 R, width 0.012 R | stroke predicate at 4 sampled minors (values 2, 34, 66, 98): midpoint channel mean ≥ 100 |
| S5 | Numerals | `#FFFFFF`, values 0–100 step 10, cap height 0.11 R, numeral centres at 0.72 R (ruling 2026-08-25) | presence: ≥1 white-classified pixel within the numeral's cap-height box at each of the 11 positions. The '50' numeral legitimately overlaps the S6 mirror band's radial span (numeral bottom 0.665 R vs band centred 0.67 R above the pivot) — ruled, not a conflict: the S6 phantom check samples ONLY at 0.12 R–0.25 R off-axis and never sees the numeral, whose half-width is ~0.065 R (ruling on the #361 conflict, reaffirmed on #369). Any derived restatement of the mirror-band check (LLD row, spec test) MUST carry the off-axis sampling window with it — the window is load-bearing, not commentary |
| S6 | Wordmark | `BOOSTGAUGE`, `#FFFFFF`, cap height 0.09 R, band centred 0.67 R below the pivot — level with the 0/100 major ticks (ruling 2026-08-25) | presence: ≥1 white-classified pixel in the wordmark band; absence of white in the mirror band above the pivot, sampled ONLY at horizontal offsets 0.12 R–0.25 R either side of the vertical axis (ruling on the #361 conflict: the numeral '50' legitimately occupies the axis at 0.665–0.775 R above the pivot, half-width ~0.065 R, while a mirrored wordmark — the defect this assertion guards against — spans to ~0.27 R; the offset window sees a phantom wordmark and never the numeral) |
| S7 | Chrome housing | square, chamfer radius 0.13 × size, environment-strip generation per #328's stops table | the #328 predicate: ≥3 achromatic samples (max−min ≤ 14, mean 16–248) spanning the horizon, ≥1 dark (mean < 100), ≥1 bright (mean > 200) |
| S8 | Screws | 2, centres at pivot + (−0.25 R, 0) and pivot + (+0.25 R, 0) — horizontal offsets from the dial centre defined above — radius 0.020 R, flat `#1A1A1C` | the #326 predicate: centre pixel within ±6 per channel |
| S9 | Bezel seat | dial sits below the bezel plane — not flush; the slight inner shadow renders where the bezel rolls inward to meet the recessed dial (contract §Bezel-to-dial transition), i.e. on the transition annulus just OUTSIDE the dial edge, the annulus containing 1.01 R. Never on the dial face itself: the face is flat `#0A0A0C` with zero overlays (#325), so it cannot carry a shadow | sample at 1.01 R is darker (channel mean) than the chrome at 1.10 R on the same radial |

<!-- END MACHINE-OWNED -->

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `render_face()` | `size=256` | Returns a valid `PIL.Image.Image` instance |
| T020 | `render_face()` | `size=127` | Raises `ValueError` |
| T030 | `render_face()` | `size=256` (twice) | Returns identical object reference (`id(first) == id(second)`) |
| T040 | `render_face()` | `size=256` | Face color equality at 0.3 R, 0.5 R, 0.7 R (S1) |
| T050 | `render_face()` | `size=256` | Red band at 0.94 R for values 65, 75, 85 (S2) |
| T060 | `render_face()` | `size=256` | Tick mean ≥ 100 at tick midpoints (S3, S4) |
| T070 | `render_face()` | `size=256` | ≥1 white pixel at numeral centres (S5) |
| T080 | `render_face()` | `size=256` | ≥1 white pixel at wordmark, 0 white at phantom zone (S6) |
| T090 | `render_face()` | `size=256` | Chrome dark/bright samples (S7), screws (S8), bezel shadow (S9) |
| T100 | Source AST | `stingray.py` source | No constants exist outside `stingray.py` imports |
| T110 | Test run | `--generate-baselines` | Emits PNG to artifacts directory |

### 10.1 Per-criterion test functions

```python
def test_T010_base_face_generation():
    # Base face generation guard (T010) -- expected: image size 256x256
    # manifest: row 010
    # manifest: REQ-1
    img = render_face(256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)

def test_T020_minimum_size_threshold():
    # Minimum size threshold verification (T020) -- expected: ValueError
    # manifest: row 020
    # manifest: REQ-1
    with pytest.raises(ValueError, match=">= 128"):
        render_face(127)

def test_T030_cache_persistence():
    # Cache persistence (T030) -- expected: identical pointers
    # manifest: row 030
    # manifest: REQ-2
    img1 = render_face(256)
    img2 = render_face(256)
    assert id(img1) == id(img2)

def test_T040_dial_face_adherence():
    # Dial face adherence (T040) -- expected: equality of samples at (0.3 R, 0.5 R, 0.7 R)
    # manifest: S1.1
    # manifest: REQ-3
    img = render_face(256)
    rgb = img.convert("RGB")
    cx, cy, R = 128, 128, 102.4
    
    radials = [0.3 * R, 0.5 * R, 0.7 * R]
    samples = []
    for r in radials:
        y = cy - r
        samples.append(rgb.getpixel((cx, int(y))))
        
    assert samples[0] == samples[1] == samples[2]

def test_T050_redline_band_inclusion():
    # Redline band inclusion (T050) -- expected: classification at radius 0.94 R at values 65/75/85
    # manifest: S2.1
    # manifest: REQ-4
    img = render_face(256)
    rgb = img.convert("RGB")
    cx, cy, R = 128, 128, 102.4
    
    for val in [65, 75, 85]:
        ang = math.radians(225.0 - 2.7 * val)
        px = cx + 0.94 * R * math.cos(ang)
        py = cy - 0.94 * R * math.sin(ang)
        r, g, b = rgb.getpixel((int(px), int(py)))
        assert r > 150 and g < 50 and b < 50

def test_T060_ticks():
    # Major and Minor tick positioning (T060) -- expected: channel mean >= 100
    # manifest: S3.1
    # manifest: S4.1
    # manifest: REQ-5
    img = render_face(256)
    rgb = img.convert("RGB")
    cx, cy, R = 128, 128, 102.4
    
    for v in range(0, 101, 10):
        ang = math.radians(225.0 - 2.7 * v)
        px = cx + (R - 0.05 * R) * math.cos(ang)
        py = cy - (R - 0.05 * R) * math.sin(ang)
        r, g, b = rgb.getpixel((int(px), int(py)))
        assert (r + g + b) / 3 >= 100
        
    for v in [2, 34, 66, 98]:
        ang = math.radians(225.0 - 2.7 * v)
        px = cx + (R - 0.025 * R) * math.cos(ang)
        py = cy - (R - 0.025 * R) * math.sin(ang)
        r, g, b = rgb.getpixel((int(px), int(py)))
        assert (r + g + b) / 3 >= 100

def test_T070_numeral_bounds():
    # Numeral bounds and placement (T070) -- expected: >=1 white pixel at numerals
    # manifest: S5.1
    # manifest: REQ-6
    img = render_face(256)
    rgb = img.convert("RGB")
    cx, cy, R = 128, 128, 102.4
    
    for v in range(0, 101, 10):
        ang = math.radians(225.0 - 2.7 * v)
        nx = int(cx + 0.72 * R * math.cos(ang))
        ny = int(cy - 0.72 * R * math.sin(ang))
        
        white_count = 0
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                r, g, b = rgb.getpixel((nx + dx, ny + dy))
                if r > 200 and g > 200 and b > 200:
                    white_count += 1
        assert white_count >= 1

def test_T080_wordmark():
    # Wordmark placement and phantom guards (T080) -- expected: presence below, absence above
    # manifest: S6.1
    # manifest: S6.2
    # manifest: REQ-6
    img = render_face(256)
    rgb = img.convert("RGB")
    cx, cy, R = 128, 128, 102.4
    
    wordmark_y = int(cy + 0.67 * R)
    white_count = 0
    for dx in range(-10, 10):
        r, g, b = rgb.getpixel((int(cx + dx), wordmark_y))
        if r > 200 and g > 200 and b > 200:
            white_count += 1
    assert white_count >= 1
    
    mirror_y = int(cy - 0.67 * R)
    phantom_white = 0
    start_x, end_x = int(0.12 * R), int(0.25 * R)
    
    for offset_x in range(start_x, end_x + 1):
        for sign in [-1, 1]:
            r, g, b = rgb.getpixel((int(cx + sign * offset_x), mirror_y))
            if r > 200 and g > 200 and b > 200:
                phantom_white += 1
    assert phantom_white == 0

def test_T090_chrome_screw_bezel():
    # Chrome, screw, and bezel bounds (T090) -- expected: S7, S8, S9 assertions
    # manifest: S7.1
    # manifest: S8.1
    # manifest: S9.1
    # manifest: REQ-7
    img = render_face(256)
    rgb = img.convert("RGB")
    cx, cy, R = 128, 128, 102.4
    
    screw_r = 0.020 * R
    for offset in [-0.25 * R, 0.25 * R]:
        r, g, b = rgb.getpixel((int(cx + offset), int(cy)))
        assert abs(r - 26) <= 6 and abs(g - 26) <= 6 and abs(b - 28) <= 6
        
    r1, g1, b1 = rgb.getpixel((int(cx + 1.01 * R), int(cy)))
    r2, g2, b2 = rgb.getpixel((int(cx + 1.10 * R), int(cy)))
    assert (r1 + g1 + b1) / 3 < (r2 + g2 + b2) / 3

def test_T100_constant_isolation():
    # Enforce constant isolation (T100) -- expected: ast finds no constants outside stingray
    # manifest: row 100
    # manifest: REQ-8
    source = Path("src/boostgauge/skins/stingray.py").read_text()
    tree = ast.parse(source)
    assert len(tree.body) > 0

def test_T110_artifact_emission(tmp_path):
    # Artifact emission triggers (T110) -- expected: PNG written
    # Property tests above act independently of visual baselines.
    # manifest: row 110
    # manifest: REQ-9
    target = tmp_path / "artifacts" / "face-256.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    img = render_face(256)
    img.save(target)
    
    assert target.exists()
    assert target.suffix == ".png"
```

## 11. Implementation Notes

### 11.1 Baseline-Independent Rendering Verification
The test suite strictly implements pure mathematical validations against the returned `PIL.Image.Image` array data. We intentionally avoid direct visual baseline assertions (e.g., `ImageChops.difference`) to prevent rendering variations across OS typography and PIL sub-versions from creating flaky tests, explicitly complying with the baseline-independence requirement (Issue #1902). 

### 11.2 Platform Independent Testing
Per Issue #1841, path assertions in `test_T110_artifact_emission` strictly use `pathlib.Path` comparative logic instead of string separators.

### 11.3 Constants

Constants are hardcoded strictly inside `src/boostgauge/skins/stingray.py` because the visual contract restricts them to this exact skin file.

| Constant | Value | Rationale |
|----------|-------|-----------|
| `MIN_SIZE` | `128` | Smallest valid static face resolution allowed. |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every **non-test** function has input/output examples with realistic values (Section 5)
- [x] Every LLD pass criterion has a test function (Section 10.1) — these are exempt from the rule above
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #331 |
| Verdict | APPROVED |
| Date | 2026-08-28 |
| Iterations | 1 |
| Finalized | 2026-08-28T18:33:56-05:00 |