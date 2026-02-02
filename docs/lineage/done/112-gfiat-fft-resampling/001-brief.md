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
