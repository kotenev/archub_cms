/* archub_overlay.js — contextual ArcHub CMS actions across the web UI. */
(function () {
  "use strict";

  if (window.__archubOverlayLoaded) return;
  window.__archubOverlayLoaded = true;

  function esc(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function actionHtml(action) {
    var cls = action.kind === "primary" ? "archub-floating__link archub-floating__link--primary" : "archub-floating__link";
    return '<a class="' + cls + '" href="' + esc(action.href) + '">' + esc(action.label) + "</a>";
  }

  function render(data) {
    if (!data || !data.enabled || !Array.isArray(data.actions) || data.actions.length === 0) return;
    if (document.getElementById("archub-floating")) return;

    var root = document.createElement("aside");
    root.id = "archub-floating";
    root.className = "archub-floating";
    root.innerHTML =
      '<button class="archub-floating__toggle" type="button" aria-expanded="false">ArcHub</button>' +
      '<div class="archub-floating__panel" hidden>' +
      '<div class="archub-floating__head">' +
      "<strong>" + esc(data.title || "ArcHub CMS") + "</strong>" +
      '<span class="muted">' +
      esc((data.summary && data.summary.nodes) || 0) +
      " nodes</span>" +
      "</div>" +
      '<div class="archub-floating__summary">' +
      '<span>draft: ' + esc((data.summary && data.summary.draft) || 0) + "</span>" +
      '<span>warn: ' + esc((data.summary && data.summary.health_warnings) || 0) + "</span>" +
      '<span>errors: ' + esc((data.summary && data.summary.health_errors) || 0) + "</span>" +
      ((data.summary && data.summary.runtime_needs_export) ? "<span>runtime stale</span>" : "") +
      "</div>" +
      '<div class="archub-floating__actions">' +
      data.actions.map(actionHtml).join("") +
      "</div>" +
      "</div>";
    document.body.appendChild(root);

    var toggle = root.querySelector(".archub-floating__toggle");
    var panel = root.querySelector(".archub-floating__panel");
    toggle.addEventListener("click", function () {
      var open = panel.hasAttribute("hidden");
      if (open) {
        panel.removeAttribute("hidden");
      } else {
        panel.setAttribute("hidden", "");
      }
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  function init() {
    var url = "/api/archub/page-context?path=" + encodeURIComponent(window.location.pathname);
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (resp) { return resp.ok ? resp.json() : null; })
      .then(render)
      .catch(function () {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
