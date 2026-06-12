const state = {
  shapes: [],
  selected: null
};

function filterCards(input) {
  const query = input.value.trim().toLowerCase();
  document.querySelectorAll("[data-search-card]").forEach((card) => {
    const text = card.textContent.toLowerCase();
    card.style.display = text.includes(query) ? "" : "none";
  });
}

function addShape(type) {
  const id = `shape-${Date.now()}-${state.shapes.length}`;
  const shape = {
    id,
    type,
    x: 80 + state.shapes.length * 32,
    y: 80 + state.shapes.length * 24,
    w: type === "decision" ? 150 : 130,
    h: type === "lane" ? 90 : 54,
    label: type.charAt(0).toUpperCase() + type.slice(1)
  };
  state.shapes.push(shape);
  renderCanvas();
}

function renderCanvas() {
  const canvas = document.querySelector("[data-diagram-canvas]");
  const mxfile = document.querySelector("[data-mxfile]");
  if (!canvas) return;
  const shapes = state.shapes.map((shape) => {
    const fill = shape.type === "decision" ? "#fef3c7" : shape.type === "lane" ? "#e0f2fe" : "#ccfbf1";
    const stroke = shape.type === "decision" ? "#d97706" : shape.type === "lane" ? "#0284c7" : "#0f766e";
    return `<g data-id="${shape.id}">
      <rect x="${shape.x}" y="${shape.y}" width="${shape.w}" height="${shape.h}" rx="6" fill="${fill}" stroke="${stroke}" stroke-width="2"></rect>
      <text x="${shape.x + 12}" y="${shape.y + 32}" fill="#0f172a" font-size="14">${escapeXml(shape.label)}</text>
    </g>`;
  }).join("");
  canvas.innerHTML = `<svg viewBox="0 0 920 540" role="img" aria-label="Diagram canvas">${shapes}</svg>`;
  if (mxfile) mxfile.value = exportMxFile();
}

function exportMxFile() {
  const cells = state.shapes.map((shape, index) => {
    return `<mxCell id="${escapeXml(shape.id)}" value="${escapeXml(shape.label)}" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1"><mxGeometry x="${shape.x}" y="${shape.y}" width="${shape.w}" height="${shape.h}" as="geometry"/></mxCell>`;
  }).join("");
  return `<mxfile host="ArcHub.ru Wiki"><diagram id="archub-demo" name="Architecture">${cells}</diagram></mxfile>`;
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-add-shape]").forEach((button) => {
    button.addEventListener("click", () => addShape(button.dataset.addShape));
  });
  const canvas = document.querySelector("[data-diagram-canvas]");
  if (canvas) {
    addShape("page");
    addShape("decision");
    addShape("lane");
  }
});
