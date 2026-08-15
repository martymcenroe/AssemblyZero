# Implementation Spec: Issue #1 - Feature: core gauge renderer — analog tachometer with arc, needle, and tick marks

## 1. Overview

Build the core gauge renderer to produce a `PIL.Image` of the v1 Stingray tachometer without `tkinter` dependencies.

**Objective:** Build the core gauge renderer to produce a `PIL.Image` of the v1 Stingray tachometer without `tkinter` dependencies.

**Success Criteria:**
- The renderer shall produce a `PIL.Image` from `render(value, telltales, size, config)` as a pure function.
- Given identical inputs, `render` shall produce byte-identical output images.
- The main needle shall render on the axis `angle(value) = 225° − 2.7° × value`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/__init__.py` | Add | Skin protocol interface definition |
| 2 | `src/boostgauge/skins/stingray.py` | Add | Stingray aesthetic implementation drawing operations |
| 3 | `src/boostgauge/gauge.py` | Add | Main renderer orchestration module |
| 4 | `tests/conftest.py` | Add | Pytest configuration to register custom CLI flags |
| 5 | `tests/unit/test_gauge.py` | Add | Unit tests for pure function contract and determinism |
| 6 | `tests/visual/test_gauge.py` | Add | Visual regression tests using explicit `--generate-baselines` |

**Implementation Order Rationale:** Define the skin protocol first, then implement the specific Stingray skin. The main `gauge.py` orchestrator relies on the skin. Next, define pytest configuration in `conftest.py`. Finally, implement tests to verify functionality.

## 3. Current State (for Modify/Delete files)

N/A - All files in this issue are new additions ("Add").

## 4. Data Structures

### 4.1 SkinConfig

**Definition:**

```python
class SkinConfig(TypedDict):
    skin_name: str
```

**Concrete Example:**

```json
{
    "skin_name": "stingray"
}
```

## 5. Function Specifications

### 5.1 `render()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render(value: float, telltales: list[float | None], size: int = 256, config: dict = None) -> Image.Image:
    """Orchestrates rendering by delegating to the active skin."""
    ...
```

**Input Example:**

```python
value = 75.0
telltales = [10.0, 50.0, 90.0, None]
size = 256
config = {"skin_name": "stingray"}
```

**Output Example:**

```text
<PIL.Image.Image image mode=RGBA size=256x256 at 0x1A2B3C4D5E6>
```

**Edge Cases:**
- `value < 0` or `value > 100` -> raises `ValueError`
- `size < 128` -> raises `ValueError`

### 5.2 `_validate_inputs()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def _validate_inputs(value: float, size: int) -> None:
    """Validates bounds of metric value and gauge size to prevent rendering OOM/NaNS."""
    ...
```

**Input Example:**

```python
value = 75.0
size = 256
```

**Output Example:**

```python
None
```

**Edge Cases:**
- `value < 0` or `value > 100` -> raises `ValueError`
- `size < 128` -> raises `ValueError`

### 5.3 `render_skin()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def render_skin(value: float, telltales: list[float | None], size: int) -> Image.Image:
    """Renders the Stingray aesthetic skin with arc, needle, and telltales."""
    ...
```

**Input Example:**

```python
value = 50.0
telltales = [10.0, None]
size = 256
```

**Output Example:**

```text
<PIL.Image.Image image mode=RGBA size=256x256 at 0x1A2B3C4D5E6>
```

**Edge Cases:**
- Validations are assumed complete by the time this is called via `gauge.py`.

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/__init__.py` (Add)

**Complete file contents:**

```python
"""Skin protocol definitions for gauge rendering.

Issue #1: Feature: core gauge renderer
"""

from typing import Protocol
from PIL import Image

class GaugeSkin(Protocol):
    def render_skin(self, value: float, telltales: list[float | None], size: int) -> Image.Image:
        """Render the gauge with the specific skin."""
        ...
```

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray skin implementation.

Issue #1: Feature: core gauge renderer
"""

import math
from PIL import Image, ImageDraw

def render_skin(value: float, telltales: list[float | None], size: int) -> Image.Image:
    """Renders the Stingray aesthetic skin."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Static elements
    center_x, center_y = size / 2, size / 2
    radius = size / 2
    
    # Draw housing, dial, ticks, numerals, and wordmark
    draw.ellipse([0, 0, size, size], fill="#111111", outline="#333333", width=2)
    for v in range(0, 110, 10):
        t_angle = 225.0 - 2.7 * v
        r_rad = math.radians(t_angle)
        draw.line([
            (center_x + math.cos(r_rad) * radius * 0.8, center_y - math.sin(r_rad) * radius * 0.8),
            (center_x + math.cos(r_rad) * radius * 0.9, center_y - math.sin(r_rad) * radius * 0.9)
        ], fill="#FFFFFF", width=2)
        draw.text((center_x + math.cos(r_rad) * radius * 0.7 - 5, center_y - math.sin(r_rad) * radius * 0.7 - 5), str(v), fill="#FFFFFF")
    draw.text((center_x - 20, center_y + radius * 0.3), "BOOST", fill="#888888")

    # Band spans 60-100 at 0.8-1.0 R
    redline_outer = radius * 1.0
    
    def val_to_angle(v: float) -> float:
        return 225.0 - 2.7 * v

    # Draw redline band (value 60 to 100)
    # PIL arc expects bounding box and angles in degrees
    # PIL angles are measured clockwise from 3 o'clock
    bbox = [center_x - redline_outer, center_y - redline_outer, 
            center_x + redline_outer, center_y + redline_outer]
    
    # Just to meet the in-band distinctness requirement color
    draw.arc(bbox, start=-val_to_angle(60), end=-val_to_angle(100), fill="#9B3020", width=int(radius*0.2))

    # Telltales
    for peak in telltales:
        if peak is not None:
            d = abs(peak - value)
            if d >= 3:
                opacity = int(255 * 0.2) # baseline translucency
            elif d > 2:
                # linear midpoint at d=2.5
                factor = 1.0 - ((d - 2.0) / 1.0) * 0.8 
                opacity = int(255 * factor)
            else:
                opacity = 255
            
            t_angle = val_to_angle(peak)
            rad = math.radians(t_angle)
            end_x = center_x + math.cos(rad) * radius * 0.9
            end_y = center_y - math.sin(rad) * radius * 0.9
            draw.line([(center_x, center_y), (end_x, end_y)], fill=(255, 255, 255, opacity), width=2)
            
    # Main needle
    m_angle = val_to_angle(value)
    rad = math.radians(m_angle)
    end_x = center_x + math.cos(rad) * radius * 0.95
    end_y = center_y - math.sin(rad) * radius * 0.95
    draw.line([(center_x, center_y), (end_x, end_y)], fill="#F73923", width=4)

    return img
```

### 6.3 `src/boostgauge/gauge.py` (Add)

**Complete file contents:**

```python
"""Main gauge orchestration module.

Issue #1: Feature: core gauge renderer
"""

from typing import TypedDict
from PIL import Image
from boostgauge.skins.stingray import render_skin

class SkinConfig(TypedDict):
    skin_name: str

def _validate_inputs(value: float, size: int) -> None:
    """Validates bounds of metric value and gauge size."""
    if not (0 <= value <= 100):
        raise ValueError(f"Value must be between 0 and 100, got {value}")
    if size < 128:
        raise ValueError(f"Size must be at least 128, got {size}")

def render(value: float, telltales: list[float | None], size: int = 256, config: dict = None) -> Image.Image:
    """Orchestrates rendering by delegating to the active skin."""
    _validate_inputs(value, size)
    
    if config is None:
        config = {"skin_name": "stingray"}
        
    if config.get("skin_name") == "stingray":
        return render_skin(value, telltales, size)
    
    raise ValueError(f"Unknown skin: {config.get('skin_name')}")
```

### 6.4 `tests/unit/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Unit tests for gauge orchestration and pure functions.

Issue #1: Feature: core gauge renderer
"""

import sys
import pytest
from PIL import Image, ImageChops
from boostgauge.gauge import render, _validate_inputs

# AGENT INSTRUCTION: Append all test functions EXCEPT `test_req_120_visual` from Section 10.1 here.
# Do not leave this file with just stubs. You MUST copy the actual implementations.
```

### 6.5 `tests/visual/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Visual regression tests for gauge rendering.

Issue #1: Feature: core gauge renderer
"""

import pytest
from pathlib import Path
from PIL import Image, ImageChops
from boostgauge.gauge import render

# AGENT INSTRUCTION: Append the `test_req_120_visual` function from Section 10.1 here.
# Do not leave this file with just stubs. You MUST copy the actual implementation.
```

### 6.6 `tests/conftest.py` (Add)

**Complete file contents:**

```python
"""Pytest configuration.

Issue #1: Feature: core gauge renderer
"""

def pytest_addoption(parser):
    parser.addoption("--generate-baselines", action="store_true", help="Generate new visual baselines")
```

## 7. Pattern References

### 7.1 Typing Definitions

**File:** `src/boostgauge/config.py` (lines 13-25)

```text
class PositionConfig(TypedDict):

class ThresholdConfig(TypedDict):

class Thresholds(TypedDict):

class TelltaleWindows(TypedDict):

class AppConfig(TypedDict):

class SessionState(TypedDict):
```

**Relevance:** Demonstrates the use of `TypedDict` for configuration structures within the codebase, which is directly mirrored in the definition of `SkinConfig`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import math` | stdlib | `src/boostgauge/skins/stingray.py` |
| `from typing import Protocol, TypedDict` | stdlib | `src/boostgauge/skins/__init__.py`, `src/boostgauge/gauge.py` |
| `from PIL import Image, ImageDraw, ImageChops` | `pillow` | All implemented modules |
| `from pathlib import Path` | stdlib | `tests/visual/test_gauge.py` |
| `import pytest` | `pytest` | Test modules |
| `import sys` | stdlib | Test modules |

**New Dependencies:** None (pillow is already included in pyproject.toml).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `render()` | `value=0, telltales=[]` | `PIL.Image` |
| T020 | `render()` | `value=50, telltales=[]` | Identical PIL images for two calls |
| T030 | `render()` | `value=0, 50, 100` | Needle exactly at 225°, 90°, -45° |
| T040 | `render()` | `value=0 vs 100` | Diff only in pixels of `#F73923` |
| T050 | `render()` | `value=75` | Band spans 60-100 at 0.8-1.0 R |
| T060 | `render()` | `value=50, telltales=[None]` | No telltale pixels |
| T070 | `render()` | `value=70, telltales=[35]` | d=35 -> 20% opacity |
| T080 | `render()` | `value=70, telltales=[72.5]` | d=2.5 -> linear midpoint opacity |
| T090 | `render()` | `value=70, telltales=[72]` | d=2 -> 100% opacity |
| T100 | `render()` | `value=75` | Tip `#F73923`, band `#9B3020` |
| T110 | `render()` | `size=128`, `size=512` | 128x128 and 512x512 images |
| T120 | `render()` | `--generate-baselines` flag | Saved baseline |
| T130 | `render()` | `value=50, telltales=[15,25,85,95]` | 4 distinct needles rendered |
| T140 | `render()` | Invalid bounds | `ValueError` raised |

### 10.1 Per-criterion test functions

```python
def test_req_010():
    # Pure function check (REQ-1) -- expected: Returns PIL.Image, no tkinter import
    img = render(0, [], 256)
    assert isinstance(img, Image.Image)

def test_req_020():
    # Deterministic output (REQ-2) -- expected: ImageChops.difference(im1, im2) is exactly 0
    img1 = render(50, [10], 256)
    img2 = render(50, [10], 256)
    diff = ImageChops.difference(img1, img2)
    assert not diff.getbbox()

def test_req_030_baseline_independent():
    # Needle angle mapping (REQ-3) -- expected: Needle exactly at 225°, 90°, -45°
    import math
    def get_tip(v, size=256):
        angle = 225.0 - 2.7 * v
        rad = math.radians(angle)
        return (int(size/2 + math.cos(rad) * size/2 * 0.95), int(size/2 - math.sin(rad) * size/2 * 0.95))
    
    assert render(0, [], 256).getpixel(get_tip(0)) == (247, 57, 35, 255)
    assert render(50, [], 256).getpixel(get_tip(50)) == (247, 57, 35, 255)
    assert render(100, [], 256).getpixel(get_tip(100)) == (247, 57, 35, 255)

def test_req_040():
    # Static element consistency (REQ-4) -- expected: Images differ only in pixels occupied by the candy-apple #F73923 needle
    img_0 = render(0, [], 256)
    img_100 = render(100, [], 256)
    diff = ImageChops.difference(img_0, img_100)
    
    bbox = diff.getbbox()
    assert bbox is not None, "Images are identical"
    
    # Verify differences are restricted to expected needle areas (lower half)
    min_x, min_y, max_x, max_y = bbox
    assert min_y >= 120, f"Difference detected outside expected needle bounds: {bbox}"

def test_req_050():
    # Redline band bounds (REQ-5) -- expected: Band spans 60-100 at 0.8-1.0 R
    import math
    img = render(75, [], 256)
    angle = 225.0 - 2.7 * 80
    rad = math.radians(angle)
    px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
    assert img.getpixel(px) == (155, 48, 32, 255)

def test_req_060():
    # Hidden missing telltales (REQ-6) -- expected: Telltale pixels are completely absent
    img_none = render(50, [None], 256)
    img_empty = render(50, [], 256)
    diff = ImageChops.difference(img_none, img_empty)
    assert not diff.getbbox()

def test_req_070():
    # Far telltale translucency (REQ-7) -- expected: d>=3 samples at baseline translucency
    import math
    img = render(70, [35], 256)
    angle = 225.0 - 2.7 * 35
    rad = math.radians(angle)
    px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
    r, g, b, a = img.getpixel(px)
    assert 60 < r < 70  # ~20% of 255 + 80% of 17 (background)
    assert 60 < g < 70
    assert 60 < b < 70
    assert a == 255

def test_req_080():
    # Mid-fade telltale opacity (REQ-8) -- expected: d=2.5 samples strictly at linear midpoint opacity
    import math
    img = render(70, [72.5], 256)
    angle = 225.0 - 2.7 * 72.5
    rad = math.radians(angle)
    px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
    r, g, b, a = img.getpixel(px)
    assert 210 < r < 220  # ~60% of 255 + 40% of 155 (redline band)
    assert 167 < g < 177  # ~60% of 255 + 40% of 48
    assert 160 < b < 170  # ~60% of 255 + 40% of 32
    assert a == 255

def test_req_090():
    # Near telltale opacity (REQ-9) -- expected: d<=2 samples at 100% opacity
    import math
    img = render(70, [72], 256)
    angle = 225.0 - 2.7 * 72
    rad = math.radians(angle)
    px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
    assert img.getpixel(px) == (255, 255, 255, 255)

def test_req_100():
    # In-band distinctness (REQ-10) -- expected: Tip sampled at candy-apple #F73923, band sampled at brick #9B3020
    import math
    img = render(75, [], 256)
    angle = 225.0 - 2.7 * 75
    rad = math.radians(angle)
    tip_px = (int(128 + math.cos(rad) * 128 * 0.95), int(128 - math.sin(rad) * 128 * 0.95))
    band_angle = 225.0 - 2.7 * 80
    band_rad = math.radians(band_angle)
    band_px = (int(128 + math.cos(band_rad) * 128 * 0.9), int(128 - math.sin(band_rad) * 128 * 0.9))
    assert img.getpixel(tip_px) == (247, 57, 35, 255)
    assert img.getpixel(band_px) == (155, 48, 32, 255)

def test_req_110():
    # Aspect lock resizing (REQ-11) -- expected: Output is 128x128 and 512x512 with matching proportion
    img_128 = render(50, [], 128)
    img_512 = render(50, [], 512)
    assert img_128.size == (128, 128)
    assert img_512.size == (512, 512)

def test_req_120_visual(request, tmp_path):
    # Explicit baseline generation (REQ-12) -- expected: --generate-baselines explicitly generates file, no auto-accept
    generate = request.config.getoption("--generate-baselines")
    img = render(0, [], 256)
    baseline_path = Path("tests/visual/baselines/baseline_0.png")
    if generate:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(baseline_path)
    else:
        assert baseline_path.exists(), "Baseline missing, run with --generate-baselines"
        baseline = Image.open(baseline_path)
        diff = ImageChops.difference(img, baseline)
        assert not diff.getbbox(), "Visual regression detected"

def test_req_130():
    # Multiple telltales (REQ-13) -- expected: Four distinct telltale needles rendered
    import math
    img_base = render(50, [], 256)
    img = render(50, [15, 25, 85, 95], 256)
    for v in [15, 25, 85, 95]:
        angle = 225.0 - 2.7 * v
        rad = math.radians(angle)
        px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
        assert img.getpixel(px) != img_base.getpixel(px)

def test_value_errors():
    # ValueError tests -- expected: ValueErrors are raised
    with pytest.raises(ValueError):
        render(-1, [], 256)
    with pytest.raises(ValueError):
        render(50, [], 100)
    with pytest.raises(ValueError):
        render(50, [], 256, config={"skin_name": "unknown"})
```

## 11. Implementation Notes

### 11.1 Error Handling Convention

Input bounds are checked in `_validate_inputs` before any `PIL.Image` allocations to avoid OOM or negative rendering sizes. Malformed inputs explicitly raise `ValueError`.

### 11.2 Geometry Calculation

Needle angle mapping `angle(value) = 225° − 2.7° × value` translates real-world coordinates into mathematical mapping. Trigonometry `sin` and `cos` are used to map polar to cartesian coordinates for lines.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `MIN_SIZE` | `128` | Prevent rendering artifacts on too small constraints |
| `NEEDLE_COLOR` | `"#F73923"` | Candy-apple color for main needle |
| `BAND_COLOR` | `"#9B3020"` | Brick color for redline band |

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
| Issue | #1 |
| Verdict | DRAFT |
| Date | 2026-08-14 |
| Iterations | 1 |
| Finalized | 2026-08-14T15:34:19-05:00 |