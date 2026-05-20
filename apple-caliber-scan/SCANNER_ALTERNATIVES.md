# Scanner Alternatives — Apple Caliber Scan

Last updated: 2026-05-17

---

## Immediate Solution (Already Working)

**Polycam Raw ZIP → this app**

The `17_05_2026.zip` you already have is a Polycam "Raw" export. Task 1 in this overhaul
implemented `load_polycam_raw_zip()` which reconstructs a fully-colored 4M+ point cloud
directly from the ZIP — no PLY subscription needed for the data you already captured.

**Export instructions (Polycam):**
1. Open the scan in Polycam → tap **Export**
2. Choose **Raw** (not "Processed" or "PLY")
3. Tap **Download** to save the `.zip`
4. Upload via the new "Prześlij plik lokalny" form in the web UI

**⚠ Subscription note:** Polycam's free tier only allows GLTF export. Raw ZIP exports
require a Pro subscription (~$13–$27/month or ~$80–$200/year as of 2026). If you need
to continue capturing new scans with Polycam's Raw format, you need a subscription.
If you switch to a free alternative below, no subscription is needed.

---

## Best Free Alternative: Scaniverse

**App:** Scaniverse — 3D Scanner (by Niantic Spatial Inc.)  
**Price:** Free (no subscription, no credit limit)  
**iOS:** Available on App Store, version 5.2.2 (updated April 2026)  
**LiDAR:** Yes — uses iPhone Pro LiDAR for real-time depth scanning  

**Export formats (all free):**
- **PLY** — colored point cloud (this app loads it directly via `load_ply()`)
- OBJ, GLB, FBX, USDZ — mesh formats (this app loads OBJ/GLB via `load_mesh()`)
- LAS — point cloud (not supported in this app yet)

**Export instructions (Scaniverse):**
1. Scan the apple crate. Walk slowly around it, ~60 cm from the top layer.
2. After capture, tap **Export** → choose **PLY** (Point Cloud)
3. Save to Files → transfer to PC (AirDrop, Files app, or iCloud)
4. Upload the `.ply` file via "Prześlij plik lokalny" in the web UI

**Quality:** LiDAR depth + RGB color, directly comparable to Polycam Raw.
Since Scaniverse uses the same iPhone LiDAR hardware, scan quality is equivalent.

---

## Paid Alternatives (If Polycam subscription is available)

### Option A: Polycam Pro + Raw ZIP (Current setup)
- **Price:** ~$13/month or ~$80/year
- **Format:** Raw ZIP → `load_polycam_raw_zip()` (4M+ colored points)
- **Advantage:** Highest point density tested; calibration ring visibility confirmed

### Option B: Record3D (One-time purchase)
- **Price:** Base app free (3 trial recordings); full version ~$7–15 one-time
- **Format:** Sequence of PLY files per frame — requires merging (not directly supported)
- **Note:** Best for dynamic capture (60 FPS LiDAR); overkill for static apple crates

---

## Comparison Table

| App | Price | PLY Export | RGB Color | LiDAR | Notes |
|-----|-------|-----------|-----------|-------|-------|
| Polycam (Raw) | ~$13/mo subscription | Via ZIP loader | ✅ Yes | ✅ Yes | User already has ZIP; highest tested quality |
| **Scaniverse** | **Free** | **✅ Direct PLY** | **✅ Yes** | **✅ Yes** | **Recommended free option** |
| 3D Scanner App | Free | ✅ PLY/PCD | ✅ Yes | ✅ Yes | No subscription required |
| KIRI Engine | Free (3 exports/week limit) | ✅ PLY | ✅ Yes | ✅ Yes | Photogrammetry + LiDAR |
| Record3D | ~$7-15 one-time | Frame-by-frame PLY | ✅ Yes | ✅ Yes | Per-frame files; not directly supported |

---

## Workflow Decision

```
Do you have a Polycam Pro subscription?
  YES → Continue using Polycam Raw ZIP → upload ZIP directly
  NO  → Switch to Scaniverse → export PLY → upload PLY directly

Scaniverse PLY is loaded by the existing load_ply() function — zero code changes needed.
```

---

## Sources

- Polycam pricing: https://poly.cam/pricing
- Polycam review 2026: https://raitly.com/tool/polycam
- Scaniverse export formats: https://community.scaniverse.com/t/which-formats-can-scaniverse-export-to/50
- Scaniverse App Store: https://apps.apple.com/us/app/scaniverse-3d-scanner/id1541433223
- 3D Scanner App: https://3dscannerapp.com/
- KIRI Engine LiDAR: https://www.kiriengine.app/features/lidar-scan
- Record3D: https://record3d.app/
