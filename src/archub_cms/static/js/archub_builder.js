(function () {
  const editor = document.getElementById("archub-builder-json");
  const root = document.querySelector(".archub-builder");
  if (!editor || !root) {
    return;
  }

  const status = document.getElementById("archub-builder-status");
  const preview = document.getElementById("archub-builder-preview");
  const audit = document.getElementById("archub-builder-audit");
  const previewButton = document.getElementById("archub-builder-preview-btn");
  const auditButton = document.getElementById("archub-builder-audit-btn");
  const formatButton = document.getElementById("archub-builder-format");
  const blockTypesJson = document.getElementById("archub-builder-block-types");
  const blueprintsJson = document.getElementById("archub-builder-blueprints");
  const previewUrl = root.dataset.previewUrl || "/admin/archub/content-builder/preview";
  const auditUrl = previewUrl.replace(/\/preview$/, "/audit");
  let blockTypes = [];
  let blueprints = [];

  try {
    blockTypes = JSON.parse((blockTypesJson && blockTypesJson.textContent) || "[]");
  } catch (_err) {
    blockTypes = [];
  }
  try {
    blueprints = JSON.parse((blueprintsJson && blueprintsJson.textContent) || "[]");
  } catch (_err) {
    blueprints = [];
  }

  const setStatus = (message, isError) => {
    if (!status) {
      return;
    }
    status.textContent = message;
    status.classList.toggle("error", Boolean(isError));
  };

  const readBlocks = () => {
    const text = editor.value.trim();
    if (!text) {
      return [];
    }
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) {
      return parsed;
    }
    if (parsed && Array.isArray(parsed.blocks)) {
      return parsed.blocks;
    }
    throw new Error("Builder JSON must be an array or an object with blocks");
  };

  const writeBlocks = (blocks) => {
    editor.value = JSON.stringify(blocks, null, 2);
  };

  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));

  const newId = () => {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID().slice(0, 12);
    }
    return Math.random().toString(36).slice(2, 12);
  };

  const addBlock = (alias) => {
    const blockType = blockTypes.find((item) => item.alias === alias);
    if (!blockType) {
      setStatus("Unknown block type", true);
      return;
    }
    let blocks;
    try {
      blocks = readBlocks();
    } catch (err) {
      setStatus(err.message, true);
      return;
    }
    const sample = JSON.parse(JSON.stringify(blockType.sample || {}));
    sample.id = newId();
    sample.order = blocks.length;
    blocks.push(sample);
    writeBlocks(blocks);
    setStatus(`Added ${blockType.name}`, false);
  };

  const applyBlueprint = (alias) => {
    const blueprint = blueprints.find((item) => item.alias === alias);
    if (!blueprint) {
      setStatus("Unknown blueprint", true);
      return;
    }
    let existing;
    try {
      existing = readBlocks();
    } catch (err) {
      setStatus(err.message, true);
      return;
    }
    if (existing.length && !window.confirm(`Replace existing blocks with "${blueprint.name}"?`)) {
      return;
    }
    writeBlocks(blueprint.blocks || []);
    setStatus(`Applied ${blueprint.name}`, false);
    renderPreview();
  };

  const formatJson = () => {
    try {
      writeBlocks(readBlocks());
      setStatus("JSON formatted", false);
    } catch (err) {
      setStatus(err.message, true);
    }
  };

  const renderAudit = (items) => {
    if (!audit) {
      return;
    }
    if (!items || !items.length) {
      audit.innerHTML = '<p class="muted">Content Builder audit has no issues.</p>';
      return;
    }
    audit.innerHTML = items.map((item) => (
      `<div class="archub-builder__audit-item archub-builder__audit-item--${escapeHtml(item.severity)}">` +
      `<strong>${escapeHtml(item.severity)}</strong><span>${escapeHtml(item.message)}</span>` +
      `<code>${escapeHtml(item.block_type)}</code></div>`
    )).join("");
  };

  const renderPreview = async () => {
    let blocks;
    try {
      blocks = readBlocks();
    } catch (err) {
      setStatus(err.message, true);
      return;
    }
    setStatus("Rendering preview...", false);
    const body = new URLSearchParams();
    body.set("blocks", JSON.stringify(blocks));
    try {
      const response = await fetch(previewUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      const payload = await response.json();
      if (!response.ok) {
        setStatus(payload.error || "Preview failed", true);
        return;
      }
      if (preview) {
        preview.innerHTML = payload.html || "";
      }
      renderAudit(payload.audit || []);
      setStatus(`Preview updated: ${payload.summary.blocks} blocks`, false);
    } catch (err) {
      setStatus(err.message || "Preview failed", true);
    }
  };

  const runAudit = async () => {
    let blocks;
    try {
      blocks = readBlocks();
    } catch (err) {
      setStatus(err.message, true);
      return;
    }
    setStatus("Running audit...", false);
    const body = new URLSearchParams();
    body.set("blocks", JSON.stringify(blocks));
    try {
      const response = await fetch(auditUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      const payload = await response.json();
      if (!response.ok) {
        setStatus(payload.error || "Audit failed", true);
        return;
      }
      renderAudit(payload.audit || []);
      setStatus(`Audit score ${payload.summary.audit_score}/100`, false);
    } catch (err) {
      setStatus(err.message || "Audit failed", true);
    }
  };

  root.querySelectorAll("[data-builder-add]").forEach((button) => {
    button.addEventListener("click", () => addBlock(button.dataset.builderAdd));
  });
  root.querySelectorAll("[data-builder-template]").forEach((button) => {
    button.addEventListener("click", () => applyBlueprint(button.dataset.builderTemplate));
  });
  if (formatButton) {
    formatButton.addEventListener("click", formatJson);
  }
  if (previewButton) {
    previewButton.addEventListener("click", renderPreview);
  }
  if (auditButton) {
    auditButton.addEventListener("click", runAudit);
  }
})();
