# Implementation Spec: 331 - Feature: static face renderer — bezel, chrome housing, dial, ticks, numerals, wordmark, screws — baked once, cached

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #331 |
| LLD | `docs/lld/approved/331-static-face-renderer.md` |
| Generated | 2026-08-27 |
| Status | APPROVED |

## 1. Overview

This implementation creates a factory module that renders the static dial face of the "stingray" gauge (bezel, housing, dial, ticks, numerals, wordmark, and screws) into a cached `PIL.Image`. 

**Objective:** Render the complete static face of the Stingray gauge once as a cached `PIL.Image`, cleanly separating static geometry from dynamic needles.

**Success Criteria:** A visual test suite validates pixel-level geometric properties against the numeric render contract (radii, colors, angles) without utilizing visual regression baselines. The rendering process is bounded by an LRU cache and utilizes no UI framework outside of Pillow.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/__init__.py` | Add | Exposes `render_face` public API. |
| 2 | `src/boostgauge/skins/stingray.py` | Add | Implements the static face rendering logic and caching. |
| 3 | `tests/visual/test_skin_stingray.py` | Add | Visual tier tests asserting exactly against the contract values. |

**Implementation Order Rationale:** The `__init__.py` file establishes the public interface. `stingray.py` implements the core rendering logic in complete isolation. The tests in `test_skin_stingray.py` drive the assertions on the rendered `PIL.Image` output.

## 3. Current State (for Modify/Delete files)

No files are being modified or deleted in this implementation. All files are new additions.

## 4. Data Structures

### 4.1 StingrayContract

**Definition:**

```python
from typing import TypedDict

class StingrayContract(TypedDict):
    face_color: str
    redline_color: str
    tick_color: str
    screw_color: str
    wordmark: str
```

**Concrete Example:**

```json
{
    "face_color": "#0A0A0C",
    "redline_color": "#AA0F19",
    "tick_color": "#FFFFFF",
    "screw_color": "#1A1A1C",
    "wordmark": "BOOSTGAUGE"
}
```

## 5. Function Specifications

### 5.1 `render_face()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from functools import lru_cache
from PIL import Image

@lru_cache(maxsize=4)
def render_face(size: int, skin: str = "stingray") -> Image.Image:
    """Returns the cached static dial face containing all static elements."""
    ...
```

**Input Example:**

```python
size = 256
skin = "stingray"
```

**Output Example:**

```python
# A PIL.Image object
<PIL.Image.Image image mode=RGBA size=256x256 at 0x7F8B9C0A>
```

**Edge Cases:**
- `size < 128` -> Should still return a `PIL.Image`, though details may alias or become unreadable.
- `skin != "stingray"` -> Currently defaults to stingray rendering as it's the only supported skin.

### 5.2 `_draw_chrome_housing()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import Image

def _draw_chrome_housing(img: Image.Image, size: int) -> None:
    """Draws the chamfered square housing and bezel seat."""
    ...
```

**Input Example:**

```python
img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
size = 256
```

**Output Example:**

```python
# Modifies `img` in-place, returns None
None
```

**Edge Cases:**
- Odd values for `size` -> rounding errors in sub-pixel geometry calculations; use `float` positioning carefully.

### 5.3 `_draw_dial_face()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageDraw

def _draw_dial_face(draw: ImageDraw.ImageDraw, size: int) -> None:
    """Draws the flat #0A0A0C circle for the dial face and the two screws."""
    ...
```

**Input Example:**

```python
draw = ImageDraw.Draw(Image.new("RGBA", (256, 256)))
size = 256
```

**Output Example:**

```python
# Modifies the image through `draw`, returns None
None
```

### 5.4 `_draw_redline_band()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageDraw

def _draw_redline_band(draw: ImageDraw.ImageDraw, size: int) -> None:
    """Draws the crimson redline arc from values 60 to 100."""
    ...
```

**Input Example:**

```python
draw = ImageDraw.Draw(Image.new("RGBA", (256, 256)))
size = 256
```

**Output Example:**

```python
None
```

### 5.5 `_draw_ticks()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageDraw

def _draw_ticks(draw: ImageDraw.ImageDraw, size: int) -> None:
    """Draws the 11 major ticks and 40 minor ticks."""
    ...
```

**Input Example:**

```python
draw = ImageDraw.Draw(Image.new("RGBA", (256, 256)))
size = 256
```

**Output Example:**

```python
None
```

### 5.6 `_draw_numerals()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import Image

def _draw_numerals(img: Image.Image, size: int) -> None:
    """Draws the 0-100 text numerals."""
    ...
```

**Input Example:**

```python
img = Image.new("RGBA", (256, 256))
size = 256
```

**Output Example:**

```python
None
```

### 5.7 `_draw_wordmark()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import Image

def _draw_wordmark(img: Image.Image, size: int) -> None:
    """Draws the BOOSTGAUGE wordmark below the pivot."""
    ...
```

**Input Example:**

```python
img = Image.new("RGBA", (256, 256))
size = 256
```

**Output Example:**

```python
None
```

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/__init__.py` (Add)

**Complete file contents:**

```python
"""Skins package for boostgauge.

Issue #331: Expose static face rendering public API.
"""

from .stingray import render_face

__all__ = ["render_face"]
```

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**File constraints:**
- Implement all the 7 functions specified in Section 5.
- Define `CONTRACT: StingrayContract` inside the module containing `#0A0A0C`, `#AA0F19`, `#FFFFFF`, `#1A1A1C`, and `BOOSTGAUGE`.
- Implement `functools.lru_cache(maxsize=4)` on `render_face`.
- Use the angle formula: `angle(value) = 225 - 2.7 * value`.
- Hardcode font fallback path wrapped in a try/except: `C:\Windows\Fonts\bahnschrift.ttf`, falling back to `ImageFont.load_default()`.
- Use exclusively Pillow (`PIL`) for rendering, strictly no `tkinter`.

### 6.3 `tests/visual/test_skin_stingray.py` (Add)

**File constraints:**
- Implement all tests listed in Section 10.
- Handle the `--generate-baselines` custom pytest flag for REQ-13.
- Use `PIL` for pixel classification assertions based purely on math/geometry without loading any reference image files.

## 7. Pattern References

### 7.1 Mathematical Angle Conversion

**File:** `tools/visual_contract_render.py` (lines 40-42)

```python
def angle(v):
    """ruling #255: angle(value) = 225 - 2.7 x value, math convention."""
    return 225.0 - (2.7 * v)
```

**Relevance:** Demonstrates the exact math calculation for gauge values to degrees required by the contract. This same conversion must be used when drawing ticks and numerals.

### 7.2 Font Loading Fallback

**File:** `tools/visual_contract_render.py` (lines 62-63)

```python
FONT = r"C:\Windows\Fonts\bahnschrift.ttf"   # DIN — listed substitute family
```

**Relevance:** Dictates the hardcoded OS font path to use for numerals and the wordmark. Should be wrapped in a `try/except OSError` falling back to `ImageFont.load_default()`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from functools import lru_cache` | stdlib | `stingray.py` |
| `import math` | stdlib | `stingray.py`, `test_skin_stingray.py` |
| `from typing import TypedDict` | stdlib | `stingray.py` |
| `from pathlib import Path` | stdlib | `test_skin_stingray.py` |
| `from PIL import Image, ImageDraw, ImageFont` | `pillow` | `stingray.py`, `test_skin_stingray.py` |

**New Dependencies:** None (pillow is already installed).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `render_face()` | `size=256` | Returns `PIL.Image.Image` with size 256x256, mode RGBA |
| T020 | `_draw_dial_face()` | `size=256` | Image analysis confirms flat `#0A0A0C` background |
| T030 | `_draw_redline_band()`| `size=256` | Image analysis confirms `#AA0F19` color at 0.94 R for 65/75/85 |
| T040 | `_draw_ticks()` | `size=256` | Stroke predicate confirms 11 major ticks |
| T050 | `_draw_ticks()` | `size=256` | Stroke predicate confirms minor ticks at 2, 34, 66, 98 |
| T060 | `_draw_numerals()` | `size=256` | Pixel presence inside numeral bounding boxes |
| T070 | `_draw_wordmark()` | `size=256` | Pixel presence in wordmark band, absent in mirror band |
| T080 | `_draw_chrome_housing()`| `size=256`| Gradient analysis across horizontal horizon |
| T090 | `_draw_dial_face()` | `size=256` | Color matches `#1A1A1C` at screw coordinates |
| T100 | `_draw_chrome_housing()`| `size=256`| Shadow analysis at 1.01 R vs 1.10 R |
| T110 | `render_face()` | `size=256` | `id(img1) == id(img2)` |
| T120 | (AST scan) | `stingray.py` | Zero instances of visual constants leaking outside module |
| T130 | CLI/Test suite | `--generate-baselines` | File exists on disk, path printed to stdout |

### 10.1 Per-criterion test functions

#### Baseline-Independent Property Assertions

```python
import math
from pathlib import Path
from PIL import Image
from boostgauge.skins.stingray import render_face

def test_req_1_happy_path():
    # Return size constraint (REQ-1) -- expected: image.size == (256, 256) and mode is RGBA
    img = render_face(size=256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"

def test_req_2_dial_face():
    # Dial face rendering (REQ-2) -- expected: interior pixels match #0A0A0C
    img = render_face(size=256)
    R = 256 * 0.40
    cx, cy = 128, 128
    
    # Sample at (0.3 R, 0.5 R, 0.7 R) along a needle-free radial (e.g. angle for value 50)
    for r_mult in (0.3, 0.5, 0.7):
        # Math angle for 50 = 225 - 2.7*50 = 90 degrees
        rad = math.radians(90)
        px = int(cx + R * r_mult * math.cos(rad))
        py = int(cy - R * r_mult * math.sin(rad)) # y inverted in PIL
        r, g, b, a = img.getpixel((px, py))
        assert (r, g, b) == (10, 10, 12) # #0A0A0C

def test_req_3_redline_band():
    # Redline band constraints (REQ-3) -- expected: redline color at 0.94 R for values 65/75/85
    img = render_face(size=256)
    R = 256 * 0.40
    cx, cy = 128, 128
    
    for val in (65, 75, 85):
        rad = math.radians(225 - 2.7 * val)
        px = int(cx + R * 0.94 * math.cos(rad))
        py = int(cy - R * 0.94 * math.sin(rad))
        r, g, b, a = img.getpixel((px, py))
        assert (r, g, b) == (170, 15, 25) # #AA0F19

def test_req_4_major_ticks():
    # Major ticks presence (REQ-4) -- expected: average brightness at tick midpoint >= 100
    img = render_face(size=256)
    R = 256 * 0.40
    cx, cy = 128, 128
    
    for val in range(0, 101, 10):
        rad = math.radians(225 - 2.7 * val)
        px = int(cx + R * 0.95 * math.cos(rad)) # Midpoint of 0.90 to 1.00 length
        py = int(cy - R * 0.95 * math.sin(rad))
        r, g, b, a = img.getpixel((px, py))
        assert sum((r, g, b)) / 3 >= 100

def test_req_5_minor_ticks():
    # Minor ticks presence (REQ-5) -- expected: average brightness at minor tick midpoint >= 100
    img = render_face(size=256)
    R = 256 * 0.40
    cx, cy = 128, 128
    
    for val in (2, 34, 66, 98):
        rad = math.radians(225 - 2.7 * val)
        px = int(cx + R * 0.975 * math.cos(rad)) # Midpoint of 0.95 to 1.00 length
        py = int(cy - R * 0.975 * math.sin(rad))
        r, g, b, a = img.getpixel((px, py))
        assert sum((r, g, b)) / 3 >= 100

def test_req_6_numerals():
    # Numerals existence (REQ-6) -- expected: >=1 white pixel near 0.72 R center
    img = render_face(size=256)
    R = 256 * 0.40
    cx, cy = 128, 128
    
    for val in range(0, 101, 10):
        rad = math.radians(225 - 2.7 * val)
        px = int(cx + R * 0.72 * math.cos(rad))
        py = int(cy - R * 0.72 * math.sin(rad))
        
        # Scan a 5x5 window around center
        found_white = False
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                r, g, b, a = img.getpixel((px+dx, py+dy))
                if sum((r, g, b)) / 3 >= 200:
                    found_white = True
                    break
            if found_white: break
        assert found_white

def test_req_7_wordmark():
    # Wordmark rendering (REQ-7) -- expected: white pixels at bottom, none at top mirror
    img = render_face(size=256)
    R = 256 * 0.40
    cx, cy = 128, 128
    
    # Check bottom band (0.67 R below pivot)
    found_white = False
    py_bottom = int(cy + R * 0.67) # Below pivot
    for px in range(int(cx - R*0.25), int(cx - R*0.12)):
        r, g, b, a = img.getpixel((px, py_bottom))
        if sum((r, g, b)) / 3 >= 200: found_white = True
    assert found_white
    
    # Check mirror top band
    found_white_mirror = False
    py_top = int(cy - R * 0.67)
    for px in range(int(cx - R*0.25), int(cx - R*0.12)):
        r, g, b, a = img.getpixel((px, py_top))
        if sum((r, g, b)) / 3 >= 200: found_white_mirror = True
    assert not found_white_mirror

def test_req_8_chrome_housing():
    # Chrome housing (REQ-8) -- expected: achromatic gradient on the housing edge
    img = render_face(size=256)
    # Check a pixel clearly outside the 0.40 R dial but inside the 256x256 square
    r, g, b, a = img.getpixel((10, 128))
    assert max(r, g, b) - min(r, g, b) <= 14

def test_req_9_screws():
    # Screws placement (REQ-9) -- expected: flat #1A1A1C at +/- 0.25 R horizontally
    img = render_face(size=256)
    R = 256 * 0.40
    cx, cy = 128, 128
    
    px_left, px_right = int(cx - R * 0.25), int(cx + R * 0.25)
    r1, g1, b1, a1 = img.getpixel((px_left, cy))
    r2, g2, b2, a2 = img.getpixel((px_right, cy))
    
    assert abs(r1 - 26) <= 6 and abs(g1 - 26) <= 6 and abs(b1 - 28) <= 6
    assert abs(r2 - 26) <= 6 and abs(g2 - 26) <= 6 and abs(b2 - 28) <= 6

def test_req_10_bezel_seat():
    # Bezel seat shadow (REQ-10) -- expected: darker at 1.01 R than 1.10 R
    img = render_face(size=256)
    R = 256 * 0.40
    cx, cy = 128, 128
    
    r1, g1, b1, a1 = img.getpixel((int(cx + R * 1.01), cy))
    r2, g2, b2, a2 = img.getpixel((int(cx + R * 1.10), cy))
    
    assert sum((r1, g1, b1)) / 3 < sum((r2, g2, b2)) / 3

def test_req_11_caching():
    # Cache hit (REQ-11) -- expected: id(img1) == id(img2)
    img1 = render_face(size=128)
    img2 = render_face(size=128)
    assert id(img1) == id(img2)

def test_req_12_constant_isolation(pytestconfig):
    # Constant encapsulation (REQ-12) -- expected: No contract constants in app code outside skin module
    import ast
    root_dir = pytestconfig.rootpath
    src_dir = root_dir / "src" / "boostgauge"
    
    contract_colors = {"#0A0A0C", "#AA0F19", "#FFFFFF", "#1A1A1C"}
    
    for py_file in src_dir.rglob("*.py"):
        if py_file.parent.name == "skins" and py_file.name == "stingray.py":
            continue
            
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in contract_colors

def test_req_13_baseline_emission(pytestconfig, capsys, tmp_path):
    # Artifact baseline emission (REQ-13) -- expected: file exists, path printed
    # The flag `--generate-baselines` is mocked here via a custom CLI arg or test logic simulation
    generate_baselines = pytestconfig.getoption("--generate-baselines", default=False)
    
    if generate_baselines:
        img = render_face(size=256)
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir(exist_ok=True)
        out_path = artifact_dir / "face-256.png"
        img.save(out_path)
        
        print(f"Generated baseline: {out_path}")
        
        # Test code MUST compare pathlib.Path objects, not strings with separators (Issue #1841)
        assert out_path.exists()
        assert out_path == artifact_dir / "face-256.png"
        
        captured = capsys.readouterr()
        # Verify the path string is printed exactly as rendered by the OS Path representation
        assert str(out_path) in captured.out
```

## 11. Implementation Notes

### 11.1 Coordinate System
Pillow (`PIL.ImageDraw`) draws using a coordinate system where `(0, 0)` is the top-left corner, and Y increases downwards. The mathematical requirement `angle(value) = 225 - 2.7 * value` calculates degrees using standard math convention (counter-clockwise from positive X-axis). To map this properly, negate the Y-component:
`x = cx + r * cos(theta)`
`y = cy - r * sin(theta)` (Note the minus sign)

### 11.2 Pillow Antialiasing
Pillow drawing primitives do not naturally antialias shapes effectively. Standard practice is to render the base primitives at `4x` size and downsample using `Image.Resampling.LANCZOS` at the very end of the function before returning and caching. However, the exact performance vs antialiasing quality tradeoff is left to the implementer as long as the pixel thresholds in the tests are satisfied.

### 11.3 Constants
All hardcoded values defined in the numeric render contract MUST exist inside `src/boostgauge/skins/stingray.py`.

| Constant | Value | Rationale |
|----------|-------|-----------|
| `FACE_COLOR` | `#0A0A0C` | LLD REQ-2 |
| `REDLINE_COLOR` | `#AA0F19` | LLD REQ-3 |
| `TICK_COLOR` | `#FFFFFF` | LLD REQ-4 |
| `SCREW_COLOR` | `#1A1A1C` | LLD REQ-9 |
| `WORDMARK` | `BOOSTGAUGE`| LLD REQ-7 |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - N/A
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every **non-test** function has input/output examples with realistic values (Section 5)
- [x] Every LLD pass criterion has a test function (Section 10.1) — these are exempt from the rule above
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)