# FFT Resampling Detection for Digital Manipulation Analysis

## User Story
As a **forensic analyst**,
I want **to detect resampling artifacts in images using FFT analysis**,
So that **I can identify images that have been digitally rotated, scaled, or otherwise manipulated**.

## Objective
Implement 2D Fast Fourier Transform analysis to detect interpolation artifacts that indicate an image has been resampled (rotated, scaled, or transformed) rather than being raw camera output.

## UX Flow

### Scenario 1: Analyze Directory of Images (Happy Path)
1. User runs `python -m src.gfiat.analyze fft ./extracted/`
2. System processes each image through 2D FFT analysis
3. System generates magnitude spectrum visualization for each image
4. System calculates anomaly scores based on periodic high-frequency spikes
5. Result: Report showing which images exhibit resampling signatures with confidence scores

### Scenario 2: Single Image Analysis with Visualization
1. User runs `python -m src.gfiat.analyze fft ./image.jpg --visualize`
2. System generates FFT magnitude spectrum
3. System saves visualization to `./output/image_fft.png`
4. Result: User can manually inspect the frequency domain for manipulation patterns

### Scenario 3: Image Too Small for Reliable Analysis
1. User runs FFT analysis on a thumbnail image (< 256x256)
2. System detects insufficient resolution for reliable frequency analysis
3. System logs warning: "Resolution < 256px: insufficient for reliable FFT analysis"
4. System returns status `SKIPPED` with reason code `LOW_RESOLUTION`
5. Result: Image excluded from analysis with clear status in report

### Scenario 4: JPEG Compression Interference
1. User analyzes heavily compressed JPEG image
2. System detects JPEG block artifacts in frequency domain
3. System adjusts anomaly threshold to account for compression artifacts
4. Result: Report notes compression level and adjusted confidence score

### Scenario 5: Decompression Bomb Protection
1. User attempts to analyze a malicious image (e.g., 1x1 pixel with huge dimensions in header)
2. System detects decoded dimensions exceed 100MP limit
3. System rejects image before full decode to prevent memory exhaustion
4. System returns status `REJECTED` with reason code `DECOMPRESSION_BOMB`
5. Result: System remains stable; attack vector neutralized

## Requirements

### FFT Analysis Core
1. Load images and convert to grayscale for frequency analysis
2. Apply 2D FFT and shift zero-frequency component to center
3. Generate log-magnitude spectrum for visualization
4. Detect periodic spikes in high-frequency regions
5. Calculate anomaly score based on deviation from expected smooth falloff

### Artifact Detection
1. Identify characteristic "star" patterns from rotation
2. Detect regular interval peaks from scaling interpolation
3. Distinguish resampling artifacts from natural image features
4. Account for JPEG compression artifacts in analysis

### Output and Reporting
1. Generate FFT visualization images for manual inspection
2. Output structured results (JSON) with anomaly scores
3. Provide human-readable summary of findings
4. Flag images exceeding anomaly threshold

### CLI Interface
1. Support directory batch processing: `python -m src.gfiat.analyze fft ./path/`
2. Support single image analysis: `python -m src.gfiat.analyze fft ./image.jpg`
3. Optional `--visualize` flag to save FFT spectrum images
4. Optional `--threshold` to adjust sensitivity
5. Optional `--output` to specify results directory

## Technical Approach
- **FFT Engine:** Use NumPy's `fft2` and `fftshift` for frequency domain conversion
- **Magnitude Spectrum:** Log-scale transformation for visualization (`np.log(np.abs(f_shift) + 1)`)
- **Peak Detection:** Analyze radial frequency distribution using local maxima finding with configurable prominence threshold; implementation may use `scipy.signal.find_peaks` or equivalent algorithm
- **Baseline Comparison:** Establish expected high-frequency falloff curve for raw camera images
- **Scoring:** Calculate deviation from baseline as normalized anomaly score (0-1)

## Risk Checklist
*Quick assessment - details go in LLD. Check all that apply and add brief notes.*

- [ ] **Architecture:** No significant architectural changes - new analysis module following existing patterns
- [x] **Cost:** Compute-intensive for large images; memory capped at 2GB per image, processing timeout at 30s
- [ ] **Legal/PII:** Images may contain sensitive content - no data leaves local system
- [ ] **Safety:** Read-only analysis; no risk of data modification

## Security Considerations
- All processing occurs locally; no external API calls
- Input validation required to prevent path traversal in CLI arguments
- Memory limits enforced (2GB cap) to prevent resource exhaustion
- Decompression bomb protection: reject images exceeding 100MP after decode

## Files to Create/Modify
- `src/gfiat/analyzers/fft_resampling.py` — Core FFT analysis implementation
- `src/gfiat/analyzers/__init__.py` — Export new analyzer
- `src/gfiat/cli/analyze.py` — Add `fft` subcommand
- `src/gfiat/utils/image_loader.py` — Shared image loading utilities (create if not exists; verify existence during implementation)
- `tests/test_fft_resampling.py` — Unit tests with known samples
- `tests/fixtures/fft/` — Test images (clean and manipulated samples)

## Dependencies
- NumPy (existing)
- OpenCV or Pillow for image loading
- SciPy (optional, for advanced peak detection)
- Matplotlib for visualization output
- **Test Data Corpus:** Synthetic test corpus will be generated as part of this issue (see Test Data Strategy below)

## Out of Scope (Future)
- **Wavelet analysis** — Complementary technique, separate issue
- **Machine learning classifier** — Train model on FFT features for higher accuracy
- **Real-time video analysis** — Frame-by-frame FFT for video forensics
- **Automatic baseline calibration** — Learn "normal" FFT from known-clean corpus

## Acceptance Criteria
- [ ] FFT magnitude spectrum generated for each input image
- [ ] Periodic high-frequency spikes detected and quantified
- [ ] Known-manipulated test images correctly flagged (rotation, scaling)
- [ ] Known-clean camera images pass without false positives
- [ ] FFT visualization saved when `--visualize` flag used
- [ ] Anomaly score output in range 0-1 with clear threshold guidance
- [ ] CLI command `python -m src.gfiat.analyze fft ./extracted/` works as specified
- [ ] Images < 256px return status `SKIPPED` with logged warning "Resolution < 256px"
- [ ] False Positive Rate < 10% on JPEG quality 60-85 test corpus (high compression)
- [ ] 12MP image processed in < 5 seconds on standard hardware (4-core, 16GB RAM)
- [ ] Memory usage capped at 2GB per image; exceeding triggers graceful failure with status `MEMORY_EXCEEDED`
- [ ] Decompression bomb images (>100MP decoded) rejected with `REJECTED` status and reason code `DECOMPRESSION_BOMB`

## Definition of Done

### Implementation
- [ ] Core FFT analysis module implemented
- [ ] Peak detection algorithm tuned with test samples
- [ ] CLI integration complete
- [ ] Unit tests written and passing (>80% coverage)
- [ ] Synthetic test corpus generated and committed to `tests/fixtures/fft/`

### Tools
- [ ] CLI tool documented with `--help` output
- [ ] Example usage added to tool documentation

### Documentation
- [ ] Algorithm explanation added to wiki
- [ ] Interpretation guide for FFT visualizations
- [ ] Update README.md with new capability
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

### Test Data Strategy
**Resolution:** No pre-existing test corpus is available. This issue includes creating a synthetic test dataset as part of the implementation scope.

The synthetic corpus will be generated programmatically using the following approach:
1. **Clean samples:** Generate synthetic "clean" images using gradient patterns and noise that simulate raw sensor characteristics
2. **Manipulated samples:** Apply known transformations (rotations: 5°, 15°, 45°, 90°; scaling: 0.5x, 1.5x, 2x) to clean samples using standard interpolation
3. **Compressed samples:** Save manipulated and clean samples at JPEG quality levels 60, 70, 85
4. **Edge cases:** Include images with natural periodic patterns (programmatically generated brick/grid patterns)

A generation script `tests/fixtures/fft/generate_corpus.py` will be created to reproducibly generate this corpus.

### Test Data Required
- **Clean samples:** Synthetically generated images simulating raw camera characteristics
- **Manipulated samples:** Images with known rotations (5°, 15°, 45°, 90°) and scaling (0.5x, 1.5x, 2x)
- **Compressed samples:** JPEG quality levels 60, 70, 85 for FPR validation
- **Edge cases:** Heavy JPEG compression, small images, images with natural periodic patterns (brick walls, fabrics)

### Manual Verification
1. Run on test corpus and review FFT visualizations
2. Verify "star" patterns visible in rotated image FFTs
3. Confirm periodic spikes present in scaled image FFTs
4. Compare scores between known-clean and known-manipulated sets

### Forcing Error States
- Use image < 64x64 to trigger resolution warning
- Use corrupted file to test error handling
- Use non-image file to test input validation
- Use decompression bomb image (e.g., 1x1 pixel with huge dimensions in header) to test memory protection
- Use image > 50MP to verify processing time limits

## Labels
`feature`, `forensics`, `domain:image-analysis`, `performance-critical`

## Effort Estimate
Medium/Large (5-8 points) — Peak detection algorithm requires tuning with test samples; includes synthetic corpus generation

## Open Questions
*None - all questions resolved inline*

## Original Brief
# G-FIAT: FFT Resampling Detection

## Problem

Digital rotation and resizing introduce periodic artifacts in the frequency domain. When an image is resampled (rotated, scaled), interpolation creates telltale patterns in the high-frequency spectrum that don't exist in raw camera sensor data.

## Proposed Solution

Implement 2D Fast Fourier Transform analysis to detect resampling artifacts indicative of digital manipulation.

### Core Functionality
- Apply 2D FFT to convert image to frequency domain
- Analyze high-frequency spectrum for periodic spikes
- Detect interpolation artifacts from rotation/scaling
- Flag images showing resampling signatures

### Algorithm
```python
def fft_resampling_check(image_path):
    # 1. Load and convert to grayscale
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    # 2. Apply 2D FFT
    f_transform = np.fft.fft2(img)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.log(np.abs(f_shift) + 1)

    # 3. Analyze for periodic spikes in high frequencies
    # Resampling creates distinctive peaks at regular intervals

    # 4. Return magnitude spectrum and anomaly score
    return magnitude, anomaly_score
```

### What Resampling Artifacts Look Like
- Raw camera images: smooth falloff in high frequencies
- Resampled images: periodic peaks/spikes in the spectrum
- Rotated images: characteristic "star" pattern in FFT

## Acceptance Criteria

- [ ] Generate FFT magnitude spectrum for each image
- [ ] Detect periodic high-frequency spikes
- [ ] Distinguish raw camera output from resampled images
- [ ] Output FFT visualization for manual inspection
- [ ] Flag images showing interpolation artifacts
- [ ] CLI: `python -m src.gfiat.analyze fft ./extracted/`

## Technical Considerations

- Requires clean comparison baseline (what does "normal" FFT look like for core photos?)
- May need calibration with known-clean and known-manipulated samples
- JPEG compression also affects high frequencies - account for this
- Consider wavelet analysis as alternative/complement
- Works best on larger images (more frequency resolution)

---

<sub>**Gemini Review:** APPROVED | **Model:** `gemini-3-pro-preview` | **Date:** 2026-02-01 | **Reviews:** 3</sub>
