function filterCards(input) {
  const query = input.value.trim().toLowerCase();
  document.querySelectorAll("[data-search-card]").forEach((card) => {
    const text = card.textContent.toLowerCase();
    card.style.display = text.includes(query) ? "" : "none";
  });
}

async function loadJson(url, target) {
  try {
    const response = await fetch(url);
    const data = await response.json();
    const node = document.querySelector(target);
    if (node) {
      node.textContent = JSON.stringify(data, null, 2);
    }
  } catch (error) {
    console.error("OLO fetch failed", error);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-load-json]").forEach((node) => {
    loadJson(node.dataset.loadJson, `#${node.id}`);
  });
});
