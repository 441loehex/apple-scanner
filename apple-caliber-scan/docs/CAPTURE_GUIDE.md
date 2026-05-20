# Capture Guide — iPhone LiDAR + Scaniverse

**Freshora Sp. Z. o. o.**

This guide covers the exact hardware setup and scanning procedure for producing scan files
suitable for apple caliber analysis.

---

## Hardware Requirements

| Item | Specification |
|------|--------------|
| iPhone | iPhone 12 Pro or newer (LiDAR required) |
| App | Scaniverse (free, App Store) |
| Measuring ring | 75 mm diameter (or documented alternative) |
| Lighting | Ambient daylight or uniform artificial light |
| Mounting | Tripod or stable hand position directly overhead |

**Supported export formats:** PLY (recommended), OBJ

---

## Before You Start

1. Fully charge the iPhone — LiDAR scanning drains battery quickly.
2. Clean the camera lens.
3. Confirm the measuring ring is undamaged and correctly labeled.
4. Note the ring size — you will need to enter it in the system if it differs from 75 mm.

---

## Scanning Procedure

### Step 1 — Place the measuring ring

Place the calibration ring flat on top of the apple layer, adjacent to a representative apple.
Do **not** cover apples with the ring — it must be fully visible and lie flat on the surface.

### Step 2 — Open Scaniverse

Launch the app → tap **New Scan**.

Select mode:
- **Object** — for a single crate (recommended for individual batches)
- **Room** — acceptable for larger pallet groups

### Step 3 — Position the iPhone

Hold the iPhone directly above the crate, camera facing down.
Recommended height: 60–90 cm above the apple surface.
The entire top layer should be visible in the frame before you start.

### Step 4 — Scan

Move **slowly** in overlapping passes across the entire top layer.
Keep the iPhone level — avoid tilting more than 30° from vertical.
Watch the Scaniverse progress indicator; continue until the mesh density indicator is stable.

**Common mistakes:**
- Moving too fast → sparse mesh → circle detection fails
- Strong shadows from one side → non-uniform depth → caliber bias
- Ring partially obscured by an apple → calibration fails

### Step 5 — Process

Wait for Scaniverse to process the scan on-device. This takes 30–120 seconds.
Do **not** close the app during processing.

### Step 6 — Export

Tap **Export** → select **PLY** (preferred) or **OBJ**.
Save to Files or share directly to Google Drive.

---

## File Naming Convention

Name the exported file with the batch number for traceability:

```
batch_042_row3_crate7.ply
```

---

## Quality Checklist

Before uploading, verify:

- [ ] Ring is clearly visible in the scan preview
- [ ] At least 15–20 apples are visible in the top layer
- [ ] No extreme lighting gradients
- [ ] File is PLY or OBJ format
- [ ] File size is between 1 MB and 200 MB

Files outside these bounds may still process, but circle detection accuracy will be lower.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "No circles detected" | Mesh too sparse | Re-scan more slowly |
| Ring not detected | Ring partially covered | Reposition ring, re-scan |
| All apples same size | Scale calibration failed | Check ring is annotated |
| Preview is black | Bad export; corrupt file | Re-export from Scaniverse |

---

## Alternative Scanners

The system accepts PLY and OBJ from any source, including:
- Polycam (iPhone/iPad)
- RealityKit Object Capture (Mac)
- Revopoint scanners

The scanning procedure above is optimized for Scaniverse + LiDAR.
Other scanners may produce better or worse results depending on mesh density.
