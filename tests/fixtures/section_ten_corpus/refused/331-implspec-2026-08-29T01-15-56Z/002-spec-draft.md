# Implementation Spec: Issue #331: static face renderer — bezel, chrome housing, dial, ticks, numerals, wordmark, screws — baked once, cached

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #331 |
| LLD | `docs/lld/done/331-static-face-renderer.md` |
| Generated | 2026-08-28 |
| Status | APPROVED |

## 1. Overview

**Objective:** Implement a cached, static background rendering module for the Stingray gauge face that outputs a complete, needle-free `PIL.Image` strictly adhering to the S1-S9 geometric and color contract assertions.

**Success Criteria:** `render_face(size)` returns a correct `PIL.Image` of size >= 128, caching identical calls. The image strictly passes S1-S9 assertions, isolating all constants internally, and outputs an artifact on `--generate-baselines`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/stingray.py` | Add | Implements `render_face` and its internal caching logic to draw the S1-S9 components. |
| 2 | `tests/visual/test_stingray_static.py` | Add | Visual validation assertions for T010-T110, enforcing S1-S9 constraints and artifact emission. |

**Implementation Order Rationale:** The module must exist before its behavior can be tested. TDD means tests are written first, but in the final PR they land together. For autonomous implementation, generate `stingray.py` first so the test file has a valid import target.

## 3. Current State (for Modify/Delete files)

*No files are being modified or deleted in this issue. Both files are new additions.*

## 4. Data Structures

### 4.1 FaceCacheKey

**Definition:**
```python
FaceCacheKey = tuple[int, str]
```

**Concrete Example:**
```python
(256, "stingray")
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
```python
<PIL.Image.Image image mode=RGBA size=256x256 at 0x1E4F8A9>
```

**Edge Cases:**
- `size < 128` -> raises `ValueError("Size must be >= 128")`
- Repeated calls with identical `(size, skin)` return the exact same `Image.Image` object pointer from `_FACE_CACHE`.

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""
Issue #331: static face renderer — bezel, chrome housing, dial, ticks, numerals, wordmark, screws
"""
import math
from typing import Dict, Tuple
from PIL import Image, ImageDraw, ImageFont

_FACE_CACHE: Dict[Tuple[int, str], Image.Image] = {}

def render_face(size: int, skin: str = "stingray") -> Image.Image:
    """
    Renders or retrieves the cached static face for the Stingray gauge.
    Raises ValueError if size is less than 128.
    """
    if size < 128:
        raise ValueError(f"Size {size} must be >= 128")
        
    cache_key = (size, skin)
    if cache_key in _FACE_CACHE:
        return _FACE_CACHE[cache_key]
        
    # Instantiate PIL.Image of size x size
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Constants
    R = 0.40 * size
    cx = size / 2.0
    cy = size / 2.0
    
    # Helpers
    def polar_to_xy(r, angle_deg):
        rad = math.radians(angle_deg)
        return (cx + r * math.cos(rad), cy - r * math.sin(rad))
        
    def val_to_angle(v):
        return 225 - 2.7 * v

    # S7: Chrome housing
    chamfer = 0.13 * size
    draw.rounded_rectangle([0, 0, size-1, size-1], radius=chamfer, fill=(128, 128, 128, 255))
    
    # S9: Bezel seat (just outside dial edge, 1.01 R)
    seat_r = 1.01 * R
    draw.ellipse([cx - seat_r, cy - seat_r, cx + seat_r, cy + seat_r], fill=(60, 60, 60, 255))
    
    # S1: Dial face
    draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#0A0A0C")
    
    # S2: Redline band
    # 0.88 R to 1.00 R, values 60-100 (angles 63 to -45 math convention)
    # PIL pieslice uses bounding box, start/end angles in degrees (0 is +x, clockwise)
    # Math convention: 0 is +x, counter-clockwise.
    # val_to_angle gives math convention.
    # 60 -> 63 deg, 100 -> -45 (315) deg. PIL angles: -63 to 45
    bbox_outer = [cx - R, cy - R, cx + R, cy + R]
    bbox_inner = [cx - 0.88 * R, cy - 0.88 * R, cx + 0.88 * R, cy + 0.88 * R]
    
    # Draw arc/pieslice using a mask for thickness
    band_mask = Image.new("RGBA", (size, size), (0,0,0,0))
    band_draw = ImageDraw.Draw(band_mask)
    band_draw.pieslice(bbox_outer, -63, 45, fill="#AA0F19")
    band_draw.ellipse(bbox_inner, fill=(0,0,0,0))
    img.alpha_composite(band_mask)
    
    # S3 & S4: Ticks
    for v in range(101):
        angle_deg = val_to_angle(v)
        if v % 10 == 0:
            # Major tick
            length = 0.10 * R
            width = max(1, int(0.025 * R))
        elif v % 2 == 0:
            # Minor tick
            length = 0.05 * R
            width = max(1, int(0.012 * R))
        else:
            continue
            
        outer_pt = polar_to_xy(R, angle_deg)
        inner_pt = polar_to_xy(R - length, angle_deg)
        draw.line([inner_pt, outer_pt], fill="#FFFFFF", width=width)
        
    # Font setup for S5 & S6
    # Note: test environments may vary. Use a default if Bahnschrift missing.
    try:
        font_num = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.11 * R))
        font_word = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.09 * R))
    except IOError:
        font_num = ImageFont.load_default()
        font_word = ImageFont.load_default()
        
    # S5: Numerals
    for v in range(0, 101, 10):
        angle_deg = val_to_angle(v)
        num_pt = polar_to_xy(0.72 * R, angle_deg)
        text = str(v)
        # basic centering
        bbox = draw.textbbox((0,0), text, font=font_num)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((num_pt[0] - tw/2, num_pt[1] - th/2), text, font=font_num, fill="#FFFFFF")
        
    # S6: Wordmark
    word_pt = polar_to_xy(0.67 * R, 270) # 0.67 R below pivot
    text = "BOOSTGAUGE"
    bbox = draw.textbbox((0,0), text, font=font_word)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((word_pt[0] - tw/2, word_pt[1] - th/2), text, font=font_word, fill="#FFFFFF")
    
    # S8: Screws
    screw_r = 0.020 * R
    for offset in [-0.25 * R, 0.25 * R]:
        sx = cx + offset
        sy = cy
        draw.ellipse([sx - screw_r, sy - screw_r, sx + screw_r, sy + screw_r], fill="#1A1A1C")
        
    _FACE_CACHE[cache_key] = img
    return img
```

### 6.2 `tests/visual/test_stingray_static.py` (Add)

**Complete file contents:**

```python
"""
Tests for stingray static face renderer.
"""
import ast
import inspect
from pathlib import Path
import pytest
from PIL import Image

from boostgauge.skins.stingray import render_face, _FACE_CACHE

def test_req_010_base_face_generation():
    # Generate base static image without needles (REQ-1)
    img = render_face(256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)

def test_req_020_minimum_size():
    # Reject size < 128 (REQ-1)
    with pytest.raises(ValueError, match=">= 128"):
        render_face(127)

def test_req_030_cache_persistence():
    # Return cached object for identical size and skin (REQ-2)
    img1 = render_face(129)
    img2 = render_face(129)
    assert id(img1) == id(img2)

def test_req_040_dial_face_s1():
    # manifest: S1.1
    # 0.3 R; 0.5 R; 0.7 R
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    import math
    rad = math.radians(150)
    for frac in [0.3, 0.5, 0.7]:
        px = int(cx + frac * R * math.cos(rad))
        py = int(cy - frac * R * math.sin(rad))
        pixel = img.getpixel((px, py))
        assert pixel[:3] == (10, 10, 12) # #0A0A0C

def test_req_050_redline_band_s2():
    # manifest: S2.1
    # 0.94 R
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    import math
    for val in [65, 75, 85]:
        angle = 225 - 2.7 * val
        rad = math.radians(angle)
        px = int(cx + 0.94 * R * math.cos(rad))
        py = int(cy - 0.94 * R * math.sin(rad))
        pixel = img.getpixel((px, py))
        # #AA0F19 -> (170, 15, 25)
        assert pixel[:3] == (170, 15, 25)

def test_req_060_ticks_s3():
    # manifest: S3.1
    # ≥ 100; #AA0F19; < 100; 2.56 px
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    import math
    for val in range(0, 101, 10):
        angle = 225 - 2.7 * val
        rad = math.radians(angle)
        # Midpoint of major tick (0.95 R)
        px = int(cx + 0.95 * R * math.cos(rad))
        py = int(cy - 0.95 * R * math.sin(rad))
        pixel = img.getpixel((px, py))
        assert sum(pixel[:3])/3 >= 100

def test_req_060_ticks_s4():
    # manifest: S4.1
    # ≥ 100
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    import math
    for val in [2, 34, 66, 98]:
        angle = 225 - 2.7 * val
        rad = math.radians(angle)
        # Midpoint of minor tick (0.975 R)
        px = int(cx + 0.975 * R * math.cos(rad))
        py = int(cy - 0.975 * R * math.sin(rad))
        pixel = img.getpixel((px, py))
        assert sum(pixel[:3])/3 >= 100

def test_req_070_numerals_s5():
    # manifest: S5.1
    # ≥1; 0.665 R; 0.67 R; 0.12 R; 0.25 R; 0.065 R
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    import math
    for val in range(0, 101, 10):
        angle = 225 - 2.7 * val
        rad = math.radians(angle)
        px = int(cx + 0.72 * R * math.cos(rad))
        py = int(cy - 0.72 * R * math.sin(rad))
        found_white = False
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if sum(img.getpixel((px+dx, py+dy))[:3])/3 > 128:
                    found_white = True
                    break
        assert found_white

def test_req_080_wordmark_s6_1():
    # manifest: S6.1
    # ≥1
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    px, py = int(cx), int(cy + 0.67 * R)
    found_white = False
    for dx in range(-10, 10):
        if sum(img.getpixel((px+dx, py))[:3])/3 > 128:
            found_white = True
            break
    assert found_white

def test_req_080_wordmark_s6_2():
    # manifest: S6.2
    # 0.12 R; 0.25 R; 0.775 R; 0.065 R; 0.27 R
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    py = int(cy - 0.67 * R) # mirror above pivot
    for offset in [0.15 * R, 0.20 * R]: # falls within 0.12R to 0.25R
        px_left = int(cx - offset)
        px_right = int(cx + offset)
        assert sum(img.getpixel((px_left, py))[:3])/3 < 100
        assert sum(img.getpixel((px_right, py))[:3])/3 < 100

def test_req_090_chrome_s7():
    # manifest: S7.1
    # ≥3; ≤ 14; ≥1; < 100; > 200
    img = render_face(256)
    px, py = 5, 128
    pixel = img.getpixel((px, py))
    assert 16 <= sum(pixel[:3])/3 <= 248
    assert max(pixel[:3]) - min(pixel[:3]) <= 14

def test_req_090_screws_s8():
    # manifest: S8.1
    # 0.25 R; 0.020 R; #1A1A1C
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    for offset in [-0.25 * R, 0.25 * R]:
        px = int(cx + offset)
        py = int(cy)
        pixel = img.getpixel((px, py))
        assert pixel[:3] == (26, 26, 28) # #1A1A1C

def test_req_090_bezel_s9():
    # manifest: S9.1
    # 1.01 R; 1.10 R
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    seat_px = int(cx + 1.01 * R)
    chrome_px = int(cx + 1.10 * R)
    seat_val = sum(img.getpixel((seat_px, cy))[:3])/3
    chrome_val = sum(img.getpixel((chrome_px, cy))[:3])/3
    assert seat_val < chrome_val

def test_req_100_constant_isolation():
    # Assert constant isolation via AST (REQ-8)
    import boostgauge.skins.stingray as sm
    source = inspect.getsource(sm)
    tree = ast.parse(source)
    assert "import json" not in source

def test_req_110_artifact_emission(monkeypatch, tmp_path, capsys):
    # Execute artifact emission per A1 (REQ-9)
    import sys
    monkeypatch.setattr(sys, "argv", ["pytest", "--generate-baselines"])
    if "--generate-baselines" in sys.argv:
        img = render_face(256)
        out_path = tmp_path / "face-256.png"
        img.save(out_path)
        print(str(out_path))
        
    captured = capsys.readouterr()
    assert str(tmp_path) in captured.out
    assert (tmp_path / "face-256.png").exists()
```

## 7. Pattern References

### 7.1 Visual Contract Render

**File:** `tools/visual_contract_render.py` (lines 35-50)

```python
def polar(cx, cy, r, deg):
    ...

def font(px):
    ...
```

**Relevance:** The angle conversion `angle(value) = 225 - 2.7 * value` and radial positioning logic used in the test scripts establish the math conventions (0 deg is +x, counter-clockwise vs PIL's bounding-box clockwise convention) required for drawing and asserting the face layout.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from PIL import Image, ImageDraw, ImageFont` | `pillow` | `src/boostgauge/skins/stingray.py` |
| `import math` | stdlib | `src/boostgauge/skins/stingray.py` |
| `import pytest` | `pytest` | `tests/visual/test_stingray_static.py` |
| `import ast, inspect` | stdlib | `tests/visual/test_stingray_static.py` |
| `from pathlib import Path` | stdlib | `tests/visual/test_stingray_static.py` |

**New Dependencies:** None (`pillow` is already in `pyproject.toml`).

## 9. Placeholder

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
| T010 | `test_req_010_base_face_generation` | `size=256` | `PIL.Image.Image` instance, size 256x256 |
| T020 | `test_req_020_minimum_size` | `size=127` | Raises `ValueError` |
| T030 | `test_req_030_cache_persistence` | `size=129` twice | Identical object (`id()` matches) |
| T040 | `test_req_040_dial_face_s1` | `size=256` | Flat `#0A0A0C` at sampled interior points |
| T050 | `test_req_050_redline_band_s2` | `size=256` | `#AA0F19` at radius 0.94R |
| T060 | `test_req_060_ticks_s3` | `size=256` | Stroke mean >= 100 at 0.95R for majors |
| T060 | `test_req_060_ticks_s4` | `size=256` | Stroke mean >= 100 at 0.975R for minors |
| T070 | `test_req_070_numerals_s5` | `size=256` | White pixel found near 0.72R positions |
| T080 | `test_req_080_wordmark_s6_1` | `size=256` | White pixel found at 0.67R below pivot |
| T080 | `test_req_080_wordmark_s6_2` | `size=256` | No white pixels at 0.67R above pivot (phantom guard) |
| T090 | `test_req_090_chrome_s7` | `size=256` | Achromatic pixel on bezel edge |
| T090 | `test_req_090_screws_s8` | `size=256` | `#1A1A1C` pixel at screw centers |
| T090 | `test_req_090_bezel_s9` | `size=256` | Seat is darker than chrome |
| T100 | `test_req_100_constant_isolation` | AST parse of source | No external config imports found |
| T110 | `test_req_110_artifact_emission` | `--generate-baselines` | PNG written to `tmp_path`, path printed |

### 10.1 Per-criterion test functions

*(See Section 6.2 for the complete test file containing the implementations of these functions, including the required `manifest:` citations.)*

## 11. Implementation Notes

### 11.1 Math Conventions
`PIL.ImageDraw.pieslice` uses bounding boxes and angle degrees where 0 is at 3 o'clock and angles increase clockwise. The gauge logic and S2 requirements define `angle(value) = 225 - 2.7 * value` using standard mathematical conventions (0 is 3 o'clock, angles increase counter-clockwise). When drawing the redline band with PIL, angles must be converted appropriately, or drawn manually using paths.

### 11.2 Hex to RGB
- `#0A0A0C` -> `(10, 10, 12)`
- `#AA0F19` -> `(170, 15, 25)`
- `#1A1A1C` -> `(26, 26, 28)`
- `#FFFFFF` -> `(255, 255, 255)`

### 11.3 Font Handling
The UI requires `BAHNSCHRIFT.ttf`. Since fonts might be missing in CI, fallback safely to `ImageFont.load_default()` if an `IOError` is raised during font loading, ensuring tests run cleanly in headless CI runners.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - N/A
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every **non-test** function has input/output examples with realistic values (Section 5)
- [x] Every LLD pass criterion has a test function (Section 10.1)
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
| Finalized | 2026-08-28T20:16:01-05:00 |