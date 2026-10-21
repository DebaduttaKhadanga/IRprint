// =====================================================================
// FUNCTIONALITY 8: Class-Wide Similarity Heat-Map (HTML5 canvas)
// =====================================================================
// Reads the scan JSON embedded by index.html and draws an N x N grid.
// Cell colour = best hybrid score between two submissions (light = 0,
// dark blue = 1). Hover shows a tooltip, click opens /pair/<id>.
(function () {
  const data = JSON.parse(document.getElementById("scan-data").textContent);
  const canvas = document.getElementById("heatmap");
  const tooltip = document.getElementById("heatmap-tooltip");
  const labels = data.labels;
  const n = labels.length;
  if (n === 0) return;

  // Single-hue sequential blue ramp (light -> dark).
  const RAMP = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
                "#256abf", "#184f95", "#0d366b"];

  function hexToRgb(hex) {
    const v = parseInt(hex.slice(1), 16);
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
  }
  function colorFor(score) {
    const t = Math.max(0, Math.min(1, score)) * (RAMP.length - 1);
    const i = Math.min(Math.floor(t), RAMP.length - 2);
    const a = hexToRgb(RAMP[i]), b = hexToRgb(RAMP[i + 1]);
    const f = t - i;
    const c = a.map((x, k) => Math.round(x + (b[k] - x) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  const css = getComputedStyle(document.documentElement);
  const textColor = css.getPropertyValue("--text-secondary").trim() || "#52514e";
  const surface = css.getPropertyValue("--surface-1").trim() || "#fcfcfb";
  const flagColor = css.getPropertyValue("--flag-text").trim() || "#9b2c0b";

  // Layout: labels on the left and top, square cells.
  const ctx = canvas.getContext("2d");
  ctx.font = "12px system-ui, sans-serif";
  const shortLabels = labels.map(l => l.length > 22 ? "…" + l.slice(-21) : l);
  const labelWidth = Math.max(...shortLabels.map(l => ctx.measureText(l).width)) + 12;
  const available = canvas.parentElement.clientWidth - labelWidth - 8;
  const cell = Math.max(18, Math.min(48, Math.floor(available / n)));
  const width = labelWidth + cell * n + 4;
  const height = labelWidth + cell * n + 4;

  const dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.width = width + "px";
  canvas.style.height = height + "px";
  ctx.scale(dpr, dpr);

  function draw() {
    ctx.fillStyle = surface;
    ctx.fillRect(0, 0, width, height);
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillStyle = textColor;
    ctx.textBaseline = "middle";

    // row labels (left)
    ctx.textAlign = "right";
    shortLabels.forEach((l, i) => ctx.fillText(l, labelWidth - 6, labelWidth + i * cell + cell / 2));
    // column labels (top, rotated)
    ctx.save();
    ctx.textAlign = "left";
    shortLabels.forEach((l, j) => {
      ctx.save();
      ctx.translate(labelWidth + j * cell + cell / 2, labelWidth - 6);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(l, 0, 0);
      ctx.restore();
    });
    ctx.restore();

    // cells, with a 2px surface gap between them
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const x = labelWidth + j * cell, y = labelWidth + i * cell;
        ctx.fillStyle = i === j ? surface : colorFor(data.matrix[i][j]);
        ctx.fillRect(x + 1, y + 1, cell - 2, cell - 2);
        if (i !== j && data.matrix[i][j] >= data.threshold) {
          ctx.strokeStyle = flagColor;
          ctx.lineWidth = 2;
          ctx.strokeRect(x + 2, y + 2, cell - 4, cell - 4);
        }
      }
    }
  }

  function cellAt(event) {
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left - labelWidth;
    const y = event.clientY - rect.top - labelWidth;
    if (x < 0 || y < 0) return null;
    const j = Math.floor(x / cell), i = Math.floor(y / cell);
    if (i >= n || j >= n || i === j) return null;
    return { i, j };
  }

  canvas.addEventListener("mousemove", (event) => {
    const hit = cellAt(event);
    if (!hit) { tooltip.style.display = "none"; canvas.style.cursor = "default"; return; }
    const score = data.matrix[hit.i][hit.j];
    tooltip.textContent = `${labels[hit.i]} ↔ ${labels[hit.j]}: ${score.toFixed(3)}`;
    tooltip.style.display = "block";
    tooltip.style.left = (event.offsetX + 14) + "px";
    tooltip.style.top = (event.offsetY + 14) + "px";
    canvas.style.cursor = data.pair_ids[hit.i][hit.j] ? "pointer" : "default";
  });
  canvas.addEventListener("mouseleave", () => { tooltip.style.display = "none"; });
  canvas.addEventListener("click", (event) => {
    const hit = cellAt(event);
    if (hit && data.pair_ids[hit.i][hit.j]) {
      window.location.href = "/pair/" + data.pair_ids[hit.i][hit.j];
    }
  });

  // legend ramp
  const legend = document.getElementById("heatmap-legend");
  if (legend) {
    const lctx = legend.getContext("2d");
    for (let x = 0; x < legend.width; x++) {
      lctx.fillStyle = colorFor(x / (legend.width - 1));
      lctx.fillRect(x, 0, 1, legend.height);
    }
  }

  draw();
})();
