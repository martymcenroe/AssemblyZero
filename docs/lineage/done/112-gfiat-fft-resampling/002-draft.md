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
3. System warns: "Image resolution too low for reliable FFT analysis"
4. Result: Image flagged as "inconclusive" rather than clean/manipulated

### Scenario 4: JPEG Compression Interference
1. User analyzes heavily compressed JPEG image
2. System detects JPEG block artifacts in frequency domain
3. System adjusts anomaly threshold to account for compression artifacts
4. Result: Report notes compression level and adjusted confidence score

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
- **Peak Detection:** Analyze radial frequency distribution for periodic anomalies
- **Baseline Comparison:** Establish expected high-frequency falloff curve for raw camera images
- **Scoring:** Calculate deviation from baseline as normalized anomaly score (0-1)

## Risk Checklist
*Quick assessment - details go in LLD. Check all that apply and add brief notes.*

- [ ] **Architecture:** No significant architectural changes - new analysis module following existing patterns
- [ ] **Cost:** Compute-intensive for large images; consider memory limits for batch processing
- [ ] **Legal/PII:** Images may contain sensitive content - no data leaves local system
- [ ] **Safety:** Read-only analysis; no risk of data modification

## Security Considerations
- All processing occurs locally; no external API calls
- Input validation required to prevent path traversal in CLI arguments
- Memory limits should be enforced for very large images to prevent DoS

## Files to Create/Modify
- `src/gfiat/analyzers/fft_resampling.py` — Core FFT analysis implementation
- `src/gfiat/analyzers/__init__.py` — Export new analyzer
- `src/gfiat/cli/analyze.py` — Add `fft` subcommand
- `src/gfiat/utils/image_loader.py` — Shared image loading utilities (if not exists)
- `tests/test_fft_resampling.py` — Unit tests with known samples
- `tests/fixtures/fft/` — Test images (clean and manipulated samples)

## Dependencies
- NumPy (existing)
- OpenCV or Pillow for image loading
- SciPy (optional, for advanced peak detection)
- Matplotlib for visualization output

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
- [ ] Low-resolution images handled gracefully with appropriate warnings
- [ ] JPEG compression artifacts don't cause excessive false positives

## Definition of Done

### Implementation
- [ ] Core FFT analysis module implemented
- [ ] Peak detection algorithm tuned with test samples
- [ ] CLI integration complete
- [ ] Unit tests written and passing (>80% coverage)

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

### Test Data Required
- **Clean samples:** Raw camera output from various devices (DSLR, phone cameras)
- **Manipulated samples:** Images with known rotations (5°, 15°, 45°, 90°) and scaling (0.5x, 1.5x, 2x)
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