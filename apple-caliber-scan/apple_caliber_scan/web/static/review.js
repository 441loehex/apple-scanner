/**
 * Apple Caliber Scan — Canvas annotation UI (two-layer: image + annotation)
 * Vanilla JS, no framework dependencies.
 */

(function () {
  "use strict";

  // Two-layer canvas: imgLayer shows the preview image; canvas overlays circles
  const imgLayer = document.getElementById("image-layer");
  const imgCtx = imgLayer.getContext("2d");
  const canvas = document.getElementById("review-canvas");
  const ctx = canvas.getContext("2d");
  const popover = document.getElementById("circle-popover");

  // State
  let circles = CIRCLES_DATA.map((c) => Object.assign({}, c));
  let imgObj = null;
  let imgNaturalW = 1, imgNaturalH = 1;
  let scale = 1;
  let selectedCircleIdx = null;
  let dragging = null;
  let addingCircle = null;
  let scaleFactor = null;
  let ringMm = RING_MM;
  let ringHighlightActive = false;

  const CALIBER_CLASSES = [
    [0, 60, "0-60"], [60, 65, "60-65"], [65, 70, "65-70"], [70, 75, "70-75"],
    [75, 80, "75-80"], [80, 85, "80-85"], [85, 90, "85-90"], [90, Infinity, "90+"],
  ];

  function classifyDiameter(d) {
    for (const [lo, hi, label] of CALIBER_CLASSES) {
      if (d >= lo && d < hi) return label;
    }
    return "90+";
  }

  function orientationLabel(o) {
    return { upright: "pionowo", sideways: "na boku", angled: "ukośnie" }[o] || "—";
  }

  function showToast(msg) {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1a5c2e;color:#fff;padding:8px 18px;border-radius:6px;z-index:9999;font-size:14px;";
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  function applyAutoRing() {
    if (!AUTO_RING) return;
    const alreadyRinged = circles.some((c) => c.is_ring);
    if (alreadyRinged) return;

    let best = null, bestDist = Infinity;
    for (const c of circles) {
      const d = Math.hypot(c.cx - AUTO_RING.cx, c.cy - AUTO_RING.cy);
      if (d < bestDist) { bestDist = d; best = c; }
    }

    if (best && bestDist < AUTO_RING.radius * 1.5) {
      best.is_ring = true;
      showToast(`Pierścień wykryty automatycznie (pewność ${(AUTO_RING.confidence * 100).toFixed(0)}%)`);
    } else {
      circles.push({
        id: null,
        cx: AUTO_RING.cx,
        cy: AUTO_RING.cy,
        radius: AUTO_RING.radius,
        is_ring: true,
        is_excluded: false,
        diameter_mm: null,
        caliber_class: null,
        confidence: AUTO_RING.confidence,
        orientation: "unknown",
      });
      showToast(`Pierścień dodany automatycznie (pewność ${(AUTO_RING.confidence * 100).toFixed(0)}%)`);
    }
    computeScale();
    drawAll();
  }

  // ── Image layer ────────────────────────────────────────────────────────────

  function drawImageLayer() {
    if (imgObj && imgObj.complete && imgObj.naturalWidth > 0) {
      imgCtx.clearRect(0, 0, imgLayer.width, imgLayer.height);
      imgCtx.drawImage(imgObj, 0, 0);
    } else {
      imgCtx.fillStyle = "#1e2e1e";
      imgCtx.fillRect(0, 0, imgLayer.width, imgLayer.height);
    }
  }

  // ── Preview controls ───────────────────────────────────────────────────────

  function applyCanvasFilter() {
    const brightness = document.getElementById("brightness-slider")?.value ?? 100;
    const contrast   = document.getElementById("contrast-slider")?.value ?? 100;
    imgLayer.style.filter = `brightness(${brightness}%) contrast(${contrast}%)`;
    const bv = document.getElementById("brightness-val");
    const cv = document.getElementById("contrast-val");
    if (bv) bv.textContent = brightness + "%";
    if (cv) cv.textContent = contrast + "%";
  }

  function highlightBlueChannel() {
    // Work on imgLayer pixels directly — annotation canvas stays untouched
    drawImageLayer();
    const imageData = imgCtx.getImageData(0, 0, imgLayer.width, imgLayer.height);
    const data = imageData.data;
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      if (b > 100 && b > r * 1.4 && b > g * 1.4) {
        data[i]     = 0;
        data[i + 1] = 255;
        data[i + 2] = 255;
      }
    }
    imgCtx.putImageData(imageData, 0, 0);
  }

  function initPreviewControls() {
    const brightnessSlider = document.getElementById("brightness-slider");
    const contrastSlider   = document.getElementById("contrast-slider");
    const ringBtn          = document.getElementById("ring-highlight-btn");
    const resetBtn         = document.getElementById("reset-view-btn");

    if (brightnessSlider) {
      brightnessSlider.addEventListener("input", applyCanvasFilter);
    }
    if (contrastSlider) {
      contrastSlider.addEventListener("input", applyCanvasFilter);
    }
    if (ringBtn) {
      ringBtn.addEventListener("click", () => {
        ringHighlightActive = !ringHighlightActive;
        ringBtn.classList.toggle("active", ringHighlightActive);
        if (ringHighlightActive) {
          highlightBlueChannel();
        } else {
          drawImageLayer();
          applyCanvasFilter();
        }
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        ringHighlightActive = false;
        const bs = document.getElementById("brightness-slider");
        const cs = document.getElementById("contrast-slider");
        if (bs) bs.value = 100;
        if (cs) cs.value = 100;
        applyCanvasFilter();
        drawImageLayer();
        if (ringBtn) ringBtn.classList.remove("active");
      });
    }
  }

  // ── Canvas load ────────────────────────────────────────────────────────────

  function loadImage() {
    resizeCanvas(1024, 1024);
    drawImageLayer();
    drawAnnotations();

    if (!PREVIEW_URL) {
      initPreviewControls();
      return;
    }

    imgObj = new Image();
    imgObj.onload = function () {
      imgNaturalW = imgObj.naturalWidth;
      imgNaturalH = imgObj.naturalHeight;
      resizeCanvas(imgNaturalW, imgNaturalH);
      drawImageLayer();
      drawAnnotations();
      initPreviewControls();
    };
    imgObj.onerror = function () {
      console.warn("Preview image failed to load:", PREVIEW_URL);
      drawAnnotations();
      initPreviewControls();
    };
    imgObj.src = PREVIEW_URL;
  }

  function resizeCanvas(w, h) {
    const container = imgLayer.parentElement;
    const displayW = container.clientWidth;
    scale = displayW / w;

    imgLayer.width  = w;
    imgLayer.height = h;
    imgLayer.style.width  = displayW + "px";
    imgLayer.style.height = Math.round(h * scale) + "px";

    canvas.width  = w;
    canvas.height = h;
    canvas.style.width  = displayW + "px";
    canvas.style.height = Math.round(h * scale) + "px";
  }

  function fromClientX(clientX) {
    const rect = canvas.getBoundingClientRect();
    return (clientX - rect.left) / (rect.width / canvas.width);
  }
  function fromClientY(clientY) {
    const rect = canvas.getBoundingClientRect();
    return (clientY - rect.top) / (rect.height / canvas.height);
  }

  function circleColor(c) {
    if (c.is_ring) return "red";
    if (c.is_excluded) return "#aaa";
    if (c.annotated) return "#1a5c2e";
    return "blue";
  }

  // ── Annotation drawing ─────────────────────────────────────────────────────

  function drawAnnotations() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    circles.forEach((c, i) => {
      const color = circleColor(c);
      ctx.beginPath();
      ctx.arc(c.cx, c.cy, c.radius, 0, Math.PI * 2);
      ctx.strokeStyle = color;
      ctx.lineWidth = i === selectedCircleIdx ? 4 : 2;
      if (c.is_excluded) {
        ctx.setLineDash([6, 4]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.stroke();
      ctx.setLineDash([]);

      if (c.is_ring) {
        ctx.fillStyle = "rgba(255,0,0,0.15)";
        ctx.fill();
        ctx.fillStyle = "red";
        ctx.font = "bold 13px sans-serif";
        ctx.fillText("PIERŚCIEŃ", c.cx + c.radius + 4, c.cy);
      }

      if (scaleFactor && !c.is_ring && !c.is_excluded) {
        const d = c.radius * 2 * scaleFactor;
        const orient = c.orientation ? ` · ${orientationLabel(c.orientation)}` : "";
        ctx.fillStyle = "#fff";
        ctx.font = "10px sans-serif";
        ctx.fillText(`${d.toFixed(0)}mm${orient}`, c.cx - 18, c.cy);
      }
    });

    if (addingCircle) {
      ctx.beginPath();
      ctx.arc(addingCircle.cx, addingCircle.cy, addingCircle.radius || 30, 0, Math.PI * 2);
      ctx.strokeStyle = "#f0b429";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    updateSidebar();
  }

  // drawAll = redraw both layers (used after state changes)
  function drawAll() {
    if (ringHighlightActive) {
      highlightBlueChannel();
    } else {
      drawImageLayer();
    }
    drawAnnotations();
  }

  // ── Hit testing ────────────────────────────────────────────────────────────

  function hitTestCircle(x, y) {
    for (let i = circles.length - 1; i >= 0; i--) {
      const c = circles[i];
      const dist = Math.hypot(x - c.cx, y - c.cy);
      if (Math.abs(dist - c.radius) < 8) return [i, "edge"];
      if (dist < c.radius) return [i, "center"];
    }
    return null;
  }

  // ── Mouse events ───────────────────────────────────────────────────────────

  canvas.addEventListener("mousedown", function (e) {
    if (e.button === 2) return;
    const x = fromClientX(e.clientX);
    const y = fromClientY(e.clientY);
    const hit = hitTestCircle(x, y);
    popover.style.display = "none";

    if (e.detail === 2 && !hit) {
      addingCircle = { startX: x, startY: y, cx: x, cy: y, radius: 1 };
      return;
    }
    if (hit) {
      const [idx, mode] = hit;
      selectedCircleIdx = idx;
      dragging = {
        idx, mode,
        startX: x, startY: y,
        origCx: circles[idx].cx, origCy: circles[idx].cy, origR: circles[idx].radius,
      };
    } else {
      selectedCircleIdx = null;
    }
    drawAnnotations();
  });

  canvas.addEventListener("mousemove", function (e) {
    const x = fromClientX(e.clientX);
    const y = fromClientY(e.clientY);

    if (addingCircle) {
      addingCircle.cx = (addingCircle.startX + x) / 2;
      addingCircle.cy = (addingCircle.startY + y) / 2;
      addingCircle.radius = Math.hypot(x - addingCircle.startX, y - addingCircle.startY) / 2;
      drawAnnotations();
      return;
    }
    if (!dragging) return;
    const dx = x - dragging.startX;
    const dy = y - dragging.startY;
    const c = circles[dragging.idx];
    if (dragging.mode === "center") {
      c.cx = dragging.origCx + dx;
      c.cy = dragging.origCy + dy;
    } else {
      c.radius = Math.max(5, Math.hypot(x - c.cx, y - c.cy));
    }
    drawAnnotations();
  });

  canvas.addEventListener("mouseup", function () {
    if (addingCircle && addingCircle.radius > 5) {
      circles.push({
        id: null,
        cx: addingCircle.cx, cy: addingCircle.cy, radius: addingCircle.radius,
        is_ring: false, is_excluded: false, confidence: 1.0,
        annotated: true, diameter_mm: null, caliber_class: null,
      });
      selectedCircleIdx = circles.length - 1;
    }
    addingCircle = null;
    dragging = null;
    drawAnnotations();
  });

  canvas.addEventListener("click", function (e) {
    const x = fromClientX(e.clientX);
    const y = fromClientY(e.clientY);
    const hit = hitTestCircle(x, y);
    if (hit && e.detail === 1) {
      const [idx] = hit;
      selectedCircleIdx = idx;
      const rect = canvas.getBoundingClientRect();
      const scaleX = rect.width / canvas.width;
      const scaleY = rect.height / canvas.height;
      popover.style.left = (rect.left + circles[idx].cx * scaleX + 10) + "px";
      popover.style.top  = (rect.top + window.scrollY + circles[idx].cy * scaleY - 20) + "px";
      popover.style.display = "block";
    } else {
      popover.style.display = "none";
    }
    drawAnnotations();
  });

  canvas.addEventListener("contextmenu", function (e) {
    e.preventDefault();
    const x = fromClientX(e.clientX);
    const y = fromClientY(e.clientY);
    const hit = hitTestCircle(x, y);
    if (hit) {
      circles.splice(hit[0], 1);
      selectedCircleIdx = null;
      popover.style.display = "none";
      drawAnnotations();
    }
  });

  // ── Actions ────────────────────────────────────────────────────────────────

  window.markCircle = function (action) {
    popover.style.display = "none";
    if (selectedCircleIdx === null) return;
    const c = circles[selectedCircleIdx];
    if (action === "ring") {
      circles.forEach((cc) => { cc.is_ring = false; });
      c.is_ring = true;
      c.is_excluded = false;
      computeScale();
    } else if (action === "apple") {
      c.is_ring = false;
      c.is_excluded = false;
      c.annotated = true;
    } else if (action === "exclude") {
      c.is_excluded = true;
      c.is_ring = false;
    }
    drawAnnotations();
  };

  function computeScale() {
    const ring = circles.find((c) => c.is_ring);
    if (!ring) { scaleFactor = null; return; }
    const ringDiamPx = ring.radius * 2;
    if (ringDiamPx < 1) { scaleFactor = null; return; }
    scaleFactor = ringMm / ringDiamPx;
    document.getElementById("scale-display").textContent = scaleFactor.toFixed(4);

    const apples = circles.filter((c) => !c.is_ring && !c.is_excluded);
    if (apples.length > 0) {
      const diams = apples.map((c) => c.radius * 2 * scaleFactor);
      const mean = diams.reduce((a, b) => a + b, 0) / diams.length;
      if (mean < 40 || mean > 120) {
        document.getElementById("confidence-display").textContent = "NISKA";
        document.getElementById("calib-warning").textContent =
          `⚠ Podejrzana średnica jabłek (${mean.toFixed(0)} mm). Sprawdź pierścień.`;
      } else {
        document.getElementById("confidence-display").textContent = "ok";
        document.getElementById("calib-warning").textContent = "";
      }
    }
  }

  function updateSidebar() {
    const counts = {};
    for (const [,, label] of CALIBER_CLASSES) counts[label] = 0;
    let total = 0;

    circles.forEach((c) => {
      if (c.is_ring || c.is_excluded || !scaleFactor) return;
      const d = c.radius * 2 * scaleFactor;
      const label = classifyDiameter(d);
      counts[label] = (counts[label] || 0) + 1;
      total++;
    });

    const tbody = document.getElementById("dist-body");
    tbody.innerHTML = "";
    let above75 = 0;

    CALIBER_CLASSES.forEach(([,, label]) => {
      const cnt = counts[label] || 0;
      const pct = total > 0 ? ((cnt / total) * 100).toFixed(1) : "0.0";
      if (["75-80", "80-85", "85-90", "90+"].includes(label)) above75 += cnt;
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${label} mm</td><td>${cnt}</td><td>${pct}%</td>`;
      tbody.appendChild(tr);
    });

    const pct75 = total > 0 ? ((above75 / total) * 100).toFixed(1) : "—";
    document.getElementById("above75-display").textContent = pct75 + (total > 0 ? "%" : "");
  }

  // ── Save annotation ────────────────────────────────────────────────────────

  document.getElementById("save-btn").addEventListener("click", async function () {
    const ring = circles.find((c) => c.is_ring);
    const payload = {
      ring_circle_id: ring ? ring.id : null,
      ring_mm: ringMm,
      circles: circles.map((c) => ({
        id: c.id, cx: c.cx, cy: c.cy, radius: c.radius,
        is_ring: c.is_ring, is_excluded: c.is_excluded,
      })),
    };
    const btn = this;
    btn.disabled = true;
    btn.textContent = "Zapisywanie...";
    try {
      const resp = await fetch(ANNOTATE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (data.status === "ok") {
        const form = document.createElement("form");
        form.method = "post";
        form.action = REPORT_URL;
        document.body.appendChild(form);
        form.submit();
      } else {
        alert("Błąd zapisu: " + JSON.stringify(data));
        btn.disabled = false;
        btn.textContent = "Zapisz adnotację i generuj raport";
      }
    } catch (err) {
      alert("Błąd sieciowy: " + err);
      btn.disabled = false;
      btn.textContent = "Zapisz adnotację i generuj raport";
    }
  });

  // Init
  loadImage();
  // Apply auto-ring after image loads (deferred so circles are drawn first)
  if (typeof AUTO_RING !== "undefined" && AUTO_RING) {
    setTimeout(applyAutoRing, 200);
  }
})();
