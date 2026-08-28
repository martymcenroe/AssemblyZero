# Implementation Spec: Issue #331 - Feature: static face renderer

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #331 |
| LLD | `docs/lld/done/331-static-face-renderer.md` |
| Generated | 2026-08-26 |
| Status | APPROVED |


## 1. Overview

**Objective:** Render the complete static face of the Stingray gauge — bezel, chrome housing, dial, ticks, numerals, wordmark, screws — as one cached `PIL.Image` without needles.

**Success Criteria:**
1. WHEN render_face(size) is called with size >= 128, the skin module shall return a PIL.Image of dimensions size x size containing every static element and no needle.
2. The system shall render each static element from the numeric render contract of docs/design/0002-aesthetic-v1-stingray.md.
3. WHEN the same (size, skin) is requested twice in one session, the system shall render once and serve the cached image thereafter.
4. The application code shall obtain the face only through the skin module's public call; no dial geometry, colour, or layout constant may exist outside the skin module.
5. WHEN the visual test tier runs with --generate-baselines, the run shall write the rendered face PNG into the run's artifacts directory AND print its path to stdout.


## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/stingray.py` | Add | Implements the static face renderer caching logic and Pillow drawing commands |
| 2 | `tests/visual/conftest.py` | Add | Implements pytest hooks and baseline generation |
| 3 | `tests/visual/test_stingray.py` | Add | Implements the visual tier tests and pixel-level constraints |

**Implementation Order Rationale:** The application code (`stingray.py`) must be implemented first since it contains the logic under test. The tests depend on the public API `render_face(size)` exposed by the skin module.


## [UNCHANGED] 3. Current State (for Modify/Delete files)


## [UNCHANGED] 4. Data Structures


### [UNCHANGED] 4.1 `_FACE_CACHE` (Global Cache Store)


## [UNCHANGED] 5. Function Specifications


### [UNCHANGED] 5.1 `render_face()`


### [UNCHANGED] 5.2 `_render_face_uncached()`


### [UNCHANGED] 5.3 `_get_font()`


### [UNCHANGED] 5.4 `_polar()`


### [UNCHANGED] 5.5 `pytest_addoption()`


### [UNCHANGED] 5.6 `pytest_sessionfinish()`


### [UNCHANGED] 5.7 `generate_baselines_if_requested()`


## 6. Change Instructions


### 6.1 `src/boostgauge/skins/stingray.py` (Add)

1. **Define Global Cache:**
```python
from PIL import Image, ImageDraw, ImageFont

_FACE_CACHE: dict[int, Image.Image] = {}
```

2. **Implement Caching Wrapper:**
```python
def render_face(size: int) -> Image.Image:
    """Returns a cached static face rendering of the given size."""
    if size not in _FACE_CACHE:
        _FACE_CACHE[size] = _render_face_uncached(size)
    return _FACE_CACHE[size]
```

3. **Implement Helpers:**
```python
import math

def _polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    """Calculate absolute (x,y) from polar coordinates."""
    rad = math.radians(deg)
    return cx + r * math.sin(rad), cy - r * math.cos(rad)

def _val_to_deg(val: float) -> float:
    """Convert gauge value to degrees."""
    # Maps 0-100 to -135 to 135 degrees
    return -135.0 + (val / 100.0) * 270.0

def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Safely load font with fallbacks."""
    for font_name in ("arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            pass
    return ImageFont.load_default()
```

4. **Implement Main Renderer:**
```python
def _render_face_uncached(size: int) -> Image.Image:
    """Renders the static face elements."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2.0, size / 2.0
    R = 0.40 * size

    # Chrome housing and bezel seat
    draw.ellipse([cx - 1.15 * R, cy - 1.15 * R, cx + 1.15 * R, cy + 1.15 * R], fill=(220, 220, 220))
    draw.ellipse([cx - 1.05 * R, cy - 1.05 * R, cx + 1.05 * R, cy + 1.05 * R], fill=(40, 40, 40))

    # Dial face
    draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(10, 10, 12))

    # Redline band (65-100)
    bbox = [cx - 0.94 * R, cy - 0.94 * R, cx + 0.94 * R, cy + 0.94 * R]
    start_angle = _val_to_deg(65) - 90
    end_angle = _val_to_deg(100) - 90
    draw.arc(bbox, start=start_angle, end=end_angle, fill=(170, 15, 25), width=int(0.02 * R))

    # Ticks and numerals
    font = _get_font(int(0.12 * R))
    for val in range(0, 101, 2):
        deg = _val_to_deg(val)
        is_major = val % 10 == 0
        r_inner = 0.85 * R if is_major else 0.91 * R
        r_outer = 0.97 * R if is_major else 0.95 * R
        
        p1 = _polar(cx, cy, r_inner, deg)
        p2 = _polar(cx, cy, r_outer, deg)
        draw.line([p1, p2], fill=(200, 200, 200), width=3 if is_major else 1)

        if is_major:
            nx, ny = _polar(cx, cy, 0.72 * R, deg)
            text = str(val)
            try:
                draw.text((nx, ny), text, fill=(255, 255, 255), font=font, anchor="mm")
            except TypeError:
                draw.text((nx - 10, ny - 10), text, fill=(255, 255, 255), font=font)

    # Wordmark
    wy = cy + 0.67 * R
    try:
        draw.text((cx, wy), "STINGRAY", fill=(255, 255, 255), font=font, anchor="mm")
    except TypeError:
        draw.text((cx - 30, wy - 10), "STINGRAY", fill=(255, 255, 255), font=font)

    # Screws
    for dx in (-0.25 * R, 0.25 * R):
        sx, sy = cx + dx, cy
        sr = 0.03 * R
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(26, 26, 28))

    return img
```


### 6.2 `tests/visual/conftest.py` (Add)

5. **Implement Pytest Hook:**
```python
def pytest_addoption(parser):
    """Add baseline generation flag."""
    parser.addoption(
        "--generate-baselines",
        action="store_true",
        help="Generate baseline images for visual tests"
    )
```

6. **Implement Baseline Generation:**
```python
def generate_baselines_if_requested(config, artifacts_dir):
    """Write face.png if --generate-baselines is passed."""
    if config.getoption("--generate-baselines"):
        from boostgauge.skins.stingray import render_face
        img = render_face(256)
        path = artifacts_dir / "face-256.png"
        img.save(path)
        print(path.resolve())

def pytest_sessionfinish(session, exitstatus):
    """Hook baseline generation into pytest after tests finish."""
    from pathlib import Path
    artifacts_dir = Path(session.config.rootdir) / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    generate_baselines_if_requested(session.config, artifacts_dir)
```


### 6.3 `tests/visual/test_stingray.py` (Add)

7. **Implement Visual Tests:**
```python
import pytest
from PIL import Image
from boostgauge.skins.stingray import render_face, _polar

# Note: The complete implementation of tests 010-130 is detailed in Section 10.1.
# This file must contain all per-criterion test functions mapping to the requirements.
```


## [UNCHANGED] 7. Pattern References


### [UNCHANGED] 7.1 Procedural Rendering Geometry


### [UNCHANGED] 7.2 Font Loading Fallbacks


## [UNCHANGED] 8. Dependencies & Imports


## 9. Placeholder

*Reserved for future use.*


## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `render_face()` | `size=256` | Object is `PIL.Image`, dimensions (256, 256), no needle rendering invoked |
| T020 | `render_face()` | `size=256` | Classification at 3 interior points + equality of samples at (0.3 R, 0.5 R, 0.7 R) to flat `#0A0A0C` |
| T030 | `render_face()` | `size=256` | Classification at radius 0.94 R at values 65/75/85 equals `#AA0F19` |
| T040 | `render_face()` | `size=256` | Stroke predicate at each tick's midpoint: channel mean >= 100, all 11 |
| T050 | `render_face()` | `size=256` | Stroke predicate at 4 sampled minors (values 2, 34, 66, 98): midpoint channel mean >= 100 |
| T060 | `render_face()` | `size=256` | >=1 white-classified pixel within numeral cap-height box at 11 positions at 0.72 R |
| T070 | `render_face()` | `size=256` | >=1 white-classified pixel in the wordmark band; absence of white in the mirror band |
| T080 | `render_face()` | `size=256` | >=3 achromatic samples spanning the horizon, >=1 dark, >=1 bright |
| T090 | `render_face()` | `size=256` | Centre pixel within +-6 per channel of `#1A1A1C` at pivot + (-0.25 R, 0) and (+0.25 R, 0) |
| T100 | `render_face()` | `size=256` | Sample at 1.01 R is darker than the chrome at 1.10 R on same radial |
| T110 | `render_face()` | `size=256` called twice | `render_face(256) is render_face(256)` is True |
| T120 | Application scan | Full source scan | AST/Regex verification ensuring values like `#AA0F19` do not appear outside `src/boostgauge/skins/` |
| T130 | `generate_baselines_if_requested()` | `--generate-baselines` | File exists in run's artifacts directory and `stdout` contains its absolute path |


### 10.1 Per-criterion test functions

#### Baseline-Independent Assertions
*Note: In accordance with template instructions, tests 020-100 validate image data purely through programmatic pixel analysis rather than matching against a baseline image, ensuring the visual specifications are met independently of self-generated baselines.*

```python
from PIL import Image
from boostgauge.skins.stingray import render_face, _polar

def test_010_basic_render_signature():
    # Basic render signature and object (REQ-1) -- expected: Object is PIL.Image, dimensions (256, 256), no needle rendering invoked
    img = render_face(256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)

def test_020_dial_face_flat_fill():
    # Dial face flat fill (REQ-2) -- expected: Classification at 3 interior points + equality of samples at (0.3 R, 0.5 R, 0.7 R) to flat #0A0A0C
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    # Baseline-independent logic checks specific radial pixels at 45 degrees
    for radius_frac in [0.3, 0.5, 0.7]:
        x, y = _polar(cx, cy, R * radius_frac, 45.0)
        assert rgb_img.getpixel((int(x), int(y))) == (10, 10, 12)

def test_030_redline_band_rendering():
    # Redline band rendering (REQ-2) -- expected: Classification at radius 0.94 R at values 65/75/85 equals #AA0F19
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    from boostgauge.skins.stingray import _val_to_deg
    for val in (65, 75, 85):
        deg = _val_to_deg(val)
        x, y = _polar(cx, cy, R * 0.94, deg)
        assert rgb_img.getpixel((int(x), int(y))) == (170, 15, 25)

def test_040_major_ticks_rendering():
    # Major ticks rendering (REQ-2) -- expected: Stroke predicate at each tick's midpoint: channel mean >= 100, all 11
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    from boostgauge.skins.stingray import _val_to_deg
    for val in range(0, 101, 10):
        deg = _val_to_deg(val)
        x, y = _polar(cx, cy, R * 0.91, deg)
        r, g, b = rgb_img.getpixel((int(x), int(y)))
        assert (r + g + b) / 3.0 >= 100

def test_050_minor_ticks_rendering():
    # Minor ticks rendering (REQ-2) -- expected: Stroke predicate at 4 sampled minors (values 2, 34, 66, 98): midpoint channel mean >= 100
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    from boostgauge.skins.stingray import _val_to_deg
    for val in (2, 34, 66, 98):
        deg = _val_to_deg(val)
        x, y = _polar(cx, cy, R * 0.93, deg)
        r, g, b = rgb_img.getpixel((round(x), round(y)))
        assert (r + g + b) / 3.0 >= 100

def test_060_numerals_presence():
    # Numerals presence (REQ-2) -- expected: >=1 white-classified pixel within the numeral's cap-height box at each of the 11 positions at 0.72 R
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    from boostgauge.skins.stingray import _val_to_deg
    for val in range(0, 101, 10):
        deg = _val_to_deg(val)
        nx, ny = _polar(cx, cy, R * 0.72, deg)
        box = (int(nx - 5), int(ny - 5), int(nx + 5), int(ny + 5))
        white_pixels = sum(1 for x in range(box[0], box[2]) for y in range(box[1], box[3]) if rgb_img.getpixel((x, y)) == (255, 255, 255))
        assert white_pixels >= 1

def test_070_wordmark_presence():
    # Wordmark presence (REQ-2) -- expected: >=1 white-classified pixel in the wordmark band; absence of white in the mirror band above the pivot, sampled ONLY at horizontal offsets 0.12 R-0.25 R either side of the vertical axis
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    # Wordmark band below pivot
    wy = cy + R * 0.67
    white_pixels = 0
    for dx in range(int(R * 0.12), int(R * 0.25) + 1):
        for side in (-1, 1):
            if rgb_img.getpixel((int(cx + side * dx), int(wy))) == (255, 255, 255):
                white_pixels += 1
    assert white_pixels >= 1
    
    # Mirror band above pivot
    my = cy - R * 0.67
    mirror_white = 0
    for dx in range(int(R * 0.12), int(R * 0.25) + 1):
        for side in (-1, 1):
            if rgb_img.getpixel((int(cx + side * dx), int(my))) == (255, 255, 255):
                mirror_white += 1
    assert mirror_white == 0

def test_080_chrome_housing_rendering():
    # Chrome housing rendering (REQ-2) -- expected: >=3 achromatic samples spanning the horizon, >=1 dark (mean < 100), >=1 bright (mean > 200)
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    
    achromatic_means = []
    # Sample spanning the horizon (y-axis center)
    for x in range(img.width):
        r, g, b = rgb_img.getpixel((x, int(cy)))
        if max(r, g, b) - min(r, g, b) <= 14:
            mean = (r + g + b) / 3.0
            if 16 <= mean <= 248:
                achromatic_means.append(mean)
                
    assert len(achromatic_means) >= 3
    assert any(m < 100 for m in achromatic_means)
    assert any(m > 200 for m in achromatic_means)

def test_090_screws_rendering():
    # Screws rendering (REQ-2) -- expected: Centre pixel within +-6 per channel of #1A1A1C at pivot + (-0.25 R, 0) and (+0.25 R, 0)
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    for dx in (-0.25 * R, 0.25 * R):
        sx, sy = cx + dx, cy
        r, g, b = rgb_img.getpixel((int(sx), int(sy)))
        assert abs(r - 26) <= 6
        assert abs(g - 26) <= 6
        assert abs(b - 28) <= 6

def test_100_bezel_seat_rendering():
    # Bezel seat rendering (REQ-2) -- expected: Sample at 1.01 R is darker (channel mean) than the chrome at 1.10 R on the same radial
    img = render_face(256)
    rgb_img = img.convert("RGB")
    cx, cy = img.width / 2.0, img.height / 2.0
    R = 0.40 * 256
    
    shadow = rgb_img.getpixel((int(cx), int(cy + R * 1.01)))
    chrome = rgb_img.getpixel((int(cx), int(cy + R * 1.10)))
    assert (sum(shadow) / 3.0) < (sum(chrome) / 3.0)

def test_110_caching_behavior():
    # Image caching verification (REQ-3) -- expected: Identical object memory reference
    img1 = render_face(256)
    img2 = render_face(256)
    assert img1 is img2

def test_120_constant_encapsulation(tmp_path):
    # Constant encapsulation check (REQ-4) -- expected: AST/Regex verification ensuring values like #AA0F19 do not appear outside src/boostgauge/skins/
    import re
    from pathlib import Path
    
    src_dir = Path(__file__).parent.parent.parent / "src" / "boostgauge"
    dial_color_pattern = re.compile(r'\(\s*(?:170\s*,\s*15\s*,\s*25|10\s*,\s*10\s*,\s*12|26\s*,\s*26\s*,\s*28)\s*\)')
    
    assert src_dir.exists(), "Source directory not found"
    for py_file in src_dir.rglob("*.py"):
        if "skins" in py_file.parts:
            continue
        content = py_file.read_text(encoding="utf-8")
        assert not dial_color_pattern.search(content), f"Dial color constant found in {py_file}"

def test_130_artifact_emission(tmp_path, capsys):
    # Artifact emission on CLI flag (REQ-5) -- expected: File exists in run's artifacts directory and stdout contains its absolute path
    import importlib.util
    from pathlib import Path
    
    spec = importlib.util.spec_from_file_location("conftest", Path(__file__).parent / "conftest.py")
    conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conftest)
    
    class MockConfig:
        def getoption(self, name, default=False):
            return True
            
    conftest.generate_baselines_if_requested(MockConfig(), Path(tmp_path))
    
    out_path = Path(tmp_path) / "face-256.png"
    captured = capsys.readouterr()
    assert out_path.exists()
    
    # MUST strictly use Path-based comparisons for platform independence
    stdout_path = Path(captured.out.strip())
    assert stdout_path.resolve() == out_path.resolve()
```


## 11. Implementation Notes


### [UNCHANGED] 11.1 Caching Granularity


### [UNCHANGED] 11.2 Mathematical Coordinate System