/*
 * ArcHub offline BPMN workflow editor — dependency-free, no network beyond the
 * ArcHub ITSM API. Statuses are BPMN user tasks; transitions are sequence flows.
 * Mount with: ArcHubBpmnEditor.mount({ container, api, data }).
 */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var NODE_W = 140, NODE_H = 70;
  var EVENT_R = 18;
  var CATS = ["todo", "in_progress", "done"];

  function el(tag, attrs, parent) {
    var node = document.createElementNS(NS, tag);
    for (var k in attrs) { if (attrs[k] != null) node.setAttribute(k, attrs[k]); }
    if (parent) parent.appendChild(node);
    return node;
  }
  function h(tag, props, parent) {
    var node = document.createElement(tag);
    for (var k in props) {
      if (k === "class") node.className = props[k];
      else if (k === "text") node.textContent = props[k];
      else node[k] = props[k];
    }
    if (parent) parent.appendChild(node);
    return node;
  }
  function slug(s) {
    return (String(s).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")) || "node";
  }

  function Editor(opts) {
    this.api = opts.api;
    var data = opts.data || {};
    this.canEdit = !!data.canEdit;
    this.schemes = data.schemes || [];
    this.custom = data.custom || [];
    this.root = typeof opts.container === "string"
      ? document.querySelector(opts.container) : opts.container;
    this.state = null;     // { key, name, statuses: {id->node}, transitions: [], initial }
    this.selected = null;
    this.linkFrom = null;
    this.drag = null;
    this._build();
    if (this.schemes.length) { this.select.value = this.schemes[0].key; this.load(this.schemes[0].key); }
    else { this.state = this._blank(); this.render(); }
  }

  Editor.prototype._build = function () {
    var self = this;
    this.root.innerHTML = "";
    this.root.classList.add("abe");
    var bar = h("div", { class: "abe__toolbar" }, this.root);

    this.select = h("select", {}, bar);
    this.schemes.forEach(function (s) {
      var custom = self.custom.indexOf(s.key) >= 0;
      h("option", { value: s.key, text: s.name + " (" + s.key + ")" + (custom ? " · custom" : " · built-in") }, self.select);
    });
    this.select.addEventListener("change", function () { self.load(self.select.value); });

    this._btn(bar, "Reload", function () { if (self.state) self.load(self.state.key); });
    if (this.canEdit) {
      this._btn(bar, "+ Status", function () { self.addStatus(); });
      this.linkBtn = this._btn(bar, "+ Transition", function () { self.toggleLinkMode(); });
      this._btn(bar, "Edit", function () { self.editSelected(); });
      this._btn(bar, "Delete", function () { self.deleteSelected(); });
      this._btn(bar, "New…", function () { self.newScheme(); });
      this._btn(bar, "Save", function () { self.save(); }, "primary");
      this._btn(bar, "Delete scheme", function () { self.deleteScheme(); });
    }
    this._btn(bar, "Export BPMN", function () { self.exportBpmn(); });

    this.hint = h("div", { class: "abe__hint", text: this.canEdit
      ? "Drag tasks to move. Double-click to edit. “+ Transition”, then click source then target."
      : "Read-only — workflow editing requires the itsm:admin role." }, this.root);
    this.status = h("div", { class: "abe__status" }, this.root);
    this.status.setAttribute("data-can-edit", this.canEdit ? "true" : "false");
    this.problems = h("ul", { class: "abe__problems" }, this.root);

    this.svg = el("svg", { class: "abe__canvas" }, this.root);
    var defs = el("defs", {}, this.svg);
    var marker = el("marker", {
      id: "abe-arrow", markerWidth: 10, markerHeight: 10, refX: 9, refY: 3,
      orient: "auto", markerUnits: "strokeWidth"
    }, defs);
    el("path", { d: "M0,0 L9,3 L0,6 Z", fill: "#495057" }, marker);
    this.layer = el("g", {}, this.svg);

    this.svg.addEventListener("pointermove", function (e) { self._onMove(e); });
    this.svg.addEventListener("pointerup", function () { self.drag = null; });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") self._cancelLink(); });
  };

  Editor.prototype._btn = function (bar, label, fn, variant) {
    var b = h("button", { class: "abe__btn" + (variant ? " abe__btn--" + variant : ""), text: label, type: "button" }, bar);
    b.addEventListener("click", fn);
    return b;
  };

  Editor.prototype.setStatus = function (msg, kind) {
    this.status.textContent = msg || "";
    this.status.className = "abe__status" + (kind ? " abe__status--" + kind : "");
    this.status.setAttribute("data-can-edit", this.canEdit ? "true" : "false");
  };
  Editor.prototype.showProblems = function (list) {
    this.problems.innerHTML = "";
    (list || []).forEach(function (p) { var li = document.createElement("li"); li.textContent = p; this.problems.appendChild(li); }, this);
  };

  Editor.prototype._blank = function () {
    return {
      key: "", name: "New workflow",
      statuses: {
        open: { id: "open", name: "Open", category: "todo", x: 120, y: 80 },
        done: { id: "done", name: "Done", category: "done", x: 420, y: 80 }
      },
      transitions: [{ id: "resolve", name: "Resolve", to: "done", froms: ["open"], global: false, conditions: [], post: [] }],
      initial: "open"
    };
  };

  Editor.prototype.load = function (key) {
    var self = this;
    this.setStatus("Loading " + key + "…"); this.showProblems([]);
    fetch(this.api + "/schemes/" + encodeURIComponent(key)).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status); return r.json();
    }).then(function (scheme) {
      self.state = self._fromScheme(scheme);
      self.selected = null; self._cancelLink();
      self._layout(); self.render();
      self.setStatus("Loaded " + key + (scheme.valid ? "" : " (currently invalid)"), scheme.valid ? "ok" : "err");
      if (!scheme.valid) self.showProblems(scheme.problems);
    }).catch(function (err) { self.setStatus("Failed to load " + key + ": " + err.message, "err"); });
  };

  Editor.prototype._fromScheme = function (scheme) {
    var statuses = {};
    (scheme.statuses || []).forEach(function (s) {
      statuses[s.id] = { id: s.id, name: s.name, category: s.category || "todo", x: 0, y: 0 };
    });
    var transitions = (scheme.transitions || []).map(function (t) {
      return {
        id: t.id, name: t.name, to: t.to_status,
        froms: (t.from_statuses || []).slice(), global: !!t.global,
        conditions: (t.conditions || []).slice(), post: (t.post_functions || []).slice()
      };
    });
    return { key: scheme.key, name: scheme.name, statuses: statuses, transitions: transitions, initial: scheme.initial_status_id };
  };

  Editor.prototype._toScheme = function () {
    var s = this.state;
    return {
      key: s.key, name: s.name, initial_status_id: s.initial,
      statuses: Object.keys(s.statuses).map(function (id) {
        var n = s.statuses[id]; return { id: n.id, name: n.name, category: n.category };
      }),
      transitions: s.transitions.map(function (t) {
        return {
          id: t.id, name: t.name, to_status: t.to,
          from_statuses: t.global ? [] : t.froms, global: t.global,
          conditions: t.conditions, post_functions: t.post
        };
      })
    };
  };

  Editor.prototype._statusList = function () {
    var s = this.state.statuses; return Object.keys(s).map(function (id) { return s[id]; });
  };
  Editor.prototype._expandedEdges = function () {
    var self = this, edges = [];
    this.state.transitions.forEach(function (t) {
      var froms = t.global ? self._statusList().map(function (n) { return n.id; }).filter(function (id) { return id !== t.to; }) : t.froms;
      froms.forEach(function (f) { if (self.state.statuses[f] && self.state.statuses[t.to]) edges.push({ from: f, to: t.to, t: t }); });
    });
    return edges;
  };

  Editor.prototype._layout = function () {
    var COL = 210, ROW = 120, OX = 120, OY = 70;
    var adj = {}, statuses = this._statusList();
    statuses.forEach(function (n) { adj[n.id] = []; });
    this._expandedEdges().forEach(function (e) { adj[e.from].push(e.to); });
    var col = {}, q = [];
    if (this.state.initial && this.state.statuses[this.state.initial]) { col[this.state.initial] = 0; q.push(this.state.initial); }
    while (q.length) { var c = q.shift(); adj[c].forEach(function (n) { if (col[n] === undefined) { col[n] = col[c] + 1; q.push(n); } }); }
    var maxCol = 0; Object.keys(col).forEach(function (k) { maxCol = Math.max(maxCol, col[k]); });
    statuses.forEach(function (n) { if (col[n.id] === undefined) col[n.id] = maxCol + 1; });
    var byCol = {};
    Object.keys(col).sort(function (a, b) { return col[a] - col[b] || a.localeCompare(b); })
      .forEach(function (id) { (byCol[col[id]] = byCol[col[id]] || []).push(id); });
    var self = this;
    Object.keys(byCol).forEach(function (c) {
      byCol[c].forEach(function (id, row) { var n = self.state.statuses[id]; n.x = OX + (+c) * COL; n.y = OY + row * ROW; });
    });
  };

  Editor.prototype._border = function (n, tox, toy) {
    var cx = n.x + NODE_W / 2, cy = n.y + NODE_H / 2, dx = tox - cx, dy = toy - cy;
    if (!dx && !dy) return { x: cx, y: cy };
    var sx = dx ? (NODE_W / 2) / Math.abs(dx) : Infinity;
    var sy = dy ? (NODE_H / 2) / Math.abs(dy) : Infinity;
    var s = Math.min(sx, sy);
    return { x: cx + dx * s, y: cy + dy * s };
  };

  Editor.prototype.render = function () {
    var self = this;
    while (this.layer.firstChild) this.layer.removeChild(this.layer.firstChild);
    var statuses = this._statusList();
    // viewBox to fit content
    var minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
    statuses.forEach(function (n) { minX = Math.min(minX, n.x); minY = Math.min(minY, n.y); maxX = Math.max(maxX, n.x + NODE_W); maxY = Math.max(maxY, n.y + NODE_H); });
    if (!statuses.length) { minX = 0; minY = 0; maxX = 400; maxY = 200; }
    this.svg.setAttribute("viewBox", (minX - 90) + " " + (minY - 50) + " " + (maxX - minX + 200) + " " + (maxY - minY + 110));

    // start event -> initial
    var init = this.state.statuses[this.state.initial];
    if (init) {
      var ex = init.x - 60, ey = init.y + NODE_H / 2;
      el("circle", { class: "abe__event", cx: ex, cy: ey, r: EVENT_R }, this.layer);
      this._edgePath(ex + EVENT_R, ey, this._border(init, ex, ey), "");
    }
    // transition edges
    this._expandedEdges().forEach(function (e) {
      var a = self.state.statuses[e.from], b = self.state.statuses[e.to];
      var p1 = self._border(a, b.x + NODE_W / 2, b.y + NODE_H / 2);
      var p2 = self._border(b, a.x + NODE_W / 2, a.y + NODE_H / 2);
      self._edgePath(p1.x, p1.y, p2, e.t.name + (e.t.global ? " *" : ""), e.t);
    });
    // end events for done statuses
    statuses.forEach(function (n) {
      if (n.category !== "done") return;
      var ex = n.x + NODE_W + 60, ey = n.y + NODE_H / 2;
      el("circle", { class: "abe__event abe__event--end", cx: ex, cy: ey, r: EVENT_R }, self.layer);
      self._edgePath(n.x + NODE_W, ey, { x: ex - EVENT_R, y: ey }, "");
    });
    // nodes
    statuses.forEach(function (n) { self._node(n); });
  };

  Editor.prototype._edgePath = function (x1, y1, p2, label, t) {
    var self = this;
    var d = "M" + x1 + "," + y1 + " L" + p2.x + "," + p2.y;
    el("path", { class: "abe__edge", d: d, "marker-end": "url(#abe-arrow)" }, this.layer);
    if (t && this.canEdit) {
      var hit = el("path", { class: "abe__edge-hit", d: d }, this.layer);
      hit.addEventListener("click", function () { self.deleteTransition(t); });
    }
    if (label) {
      el("text", { class: "abe__edge-label", x: (x1 + p2.x) / 2, y: (y1 + p2.y) / 2 - 4, "text-anchor": "middle" }, this.layer).textContent = label;
    }
  };

  Editor.prototype._node = function (n) {
    var self = this;
    var cls = "abe__node abe__node--" + n.category + (this.selected === n.id ? " abe__node--selected" : "");
    var g = el("g", { class: cls, transform: "translate(" + n.x + "," + n.y + ")" }, this.layer);
    el("rect", { class: "abe__node-box", x: 0, y: 0, width: NODE_W, height: NODE_H, rx: 10 }, g);
    var label = el("text", { class: "abe__node-label", x: NODE_W / 2, y: NODE_H / 2, "text-anchor": "middle" }, g);
    label.textContent = n.name + (n.id === this.state.initial ? " ◆" : "");
    el("text", { class: "abe__node-cat", x: NODE_W / 2, y: NODE_H - 12, "text-anchor": "middle" }, g).textContent = n.category;
    g.addEventListener("pointerdown", function (e) { self._onNodeDown(e, n); });
    g.addEventListener("dblclick", function () { self.selected = n.id; self.editSelected(); });
  };

  Editor.prototype._toSvg = function (e) {
    var pt = this.svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    var m = this.svg.getScreenCTM(); return m ? pt.matrixTransform(m.inverse()) : { x: e.clientX, y: e.clientY };
  };
  Editor.prototype._onNodeDown = function (e, n) {
    this.selected = n.id;
    if (this.linkFrom) { this._completeLink(n); this.render(); return; }
    if (!this.canEdit) { this.render(); return; }
    var p = this._toSvg(e);
    this.drag = { id: n.id, dx: p.x - n.x, dy: p.y - n.y };
    this.render();
  };
  Editor.prototype._onMove = function (e) {
    if (!this.drag) return;
    var p = this._toSvg(e), n = this.state.statuses[this.drag.id];
    if (!n) return; n.x = p.x - this.drag.dx; n.y = p.y - this.drag.dy; this.render();
  };

  Editor.prototype._uid = function (base, used) {
    var id = base, i = 2; while (used[id]) { id = base + "_" + i; i++; } return id;
  };
  Editor.prototype.addStatus = function () {
    var name = (prompt("New status name:", "New Status") || "").trim(); if (!name) return;
    var cat = (prompt("Category (" + CATS.join(" / ") + "):", "todo") || "todo").trim();
    if (CATS.indexOf(cat) < 0) cat = "todo";
    var id = this._uid(slug(name), this.state.statuses);
    this.state.statuses[id] = { id: id, name: name, category: cat, x: 140, y: 140 };
    if (!this.state.initial) this.state.initial = id;
    this.selected = id; this.render();
  };
  Editor.prototype.editSelected = function () {
    var n = this.selected && this.state.statuses[this.selected]; if (!n) { this.setStatus("Select a status first.", "err"); return; }
    var name = (prompt("Status name:", n.name) || "").trim(); if (name) n.name = name;
    var cat = (prompt("Category (" + CATS.join(" / ") + "):", n.category) || n.category).trim();
    if (CATS.indexOf(cat) >= 0) n.category = cat;
    if (confirm("Make '" + n.name + "' the initial status?")) this.state.initial = n.id;
    this.render();
  };
  Editor.prototype.deleteSelected = function () {
    var id = this.selected; if (!id || !this.state.statuses[id]) { this.setStatus("Select a status first.", "err"); return; }
    if (!confirm("Delete status '" + this.state.statuses[id].name + "' and its transitions?")) return;
    delete this.state.statuses[id];
    this.state.transitions = this.state.transitions.filter(function (t) {
      if (t.to === id) return false; t.froms = t.froms.filter(function (f) { return f !== id; });
      return t.global || t.froms.length;
    });
    if (this.state.initial === id) { var rest = this._statusList(); this.state.initial = rest.length ? rest[0].id : ""; }
    this.selected = null; this.render();
  };

  Editor.prototype.toggleLinkMode = function () {
    if (this.linkFrom) { this._cancelLink(); return; }
    if (!this.selected) { this.setStatus("Select the source status, then click “+ Transition”, then the target.", "err"); return; }
    this.linkFrom = this.selected; this.root.classList.add("abe__linking");
    if (this.linkBtn) this.linkBtn.classList.add("abe__btn--primary");
    this.setStatus("Linking from '" + this.state.statuses[this.linkFrom].name + "' — click the target status (Esc to cancel).");
  };
  Editor.prototype._cancelLink = function () {
    this.linkFrom = null; this.root.classList.remove("abe__linking");
    if (this.linkBtn) this.linkBtn.classList.remove("abe__btn--primary");
  };
  Editor.prototype._completeLink = function (target) {
    var from = this.linkFrom; this._cancelLink();
    if (!from || from === target.id) { this.setStatus("Pick a different target status.", "err"); return; }
    var name = (prompt("Transition name:", "Move") || "").trim(); if (!name) return;
    var id = this._uid(slug(name), this._txIndex());
    this.state.transitions.push({ id: id, name: name, to: target.id, froms: [from], global: false, conditions: [], post: [] });
    this.setStatus("Added transition '" + name + "'.", "ok");
  };
  Editor.prototype._txIndex = function () { var m = {}; this.state.transitions.forEach(function (t) { m[t.id] = true; }); return m; };
  Editor.prototype.deleteTransition = function (t) {
    if (!this.canEdit) return;
    if (!confirm("Delete transition '" + t.name + "'?")) return;
    this.state.transitions = this.state.transitions.filter(function (x) { return x !== t; });
    this.render();
  };

  Editor.prototype.newScheme = function () {
    var key = (prompt("New workflow key (a-z, 0-9, _):", "custom_workflow") || "").trim(); if (!key) return;
    this.state = this._blank(); this.state.key = slug(key); this.state.name = (prompt("Display name:", key) || key).trim();
    this.selected = null; this._cancelLink(); this.render();
    this.setStatus("New workflow — model it, then Save.", "ok");
  };

  Editor.prototype.save = function () {
    var self = this;
    if (!this.state.key) { var k = (prompt("Workflow key:", "custom_workflow") || "").trim(); if (!k) return; this.state.key = slug(k); }
    this.setStatus("Saving " + this.state.key + "…"); this.showProblems([]);
    fetch(this.api + "/schemes", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(this._toScheme())
    }).then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
      .then(function (res) {
        if (res.status === 201) {
          self.setStatus("Saved workflow " + res.body.key + " (" + res.body.statuses.length + " statuses, " + res.body.transitions.length + " transitions).", "ok");
          if (!self.schemes.some(function (s) { return s.key === res.body.key; })) {
            self.schemes.push(res.body); self.custom.push(res.body.key);
            h("option", { value: res.body.key, text: res.body.name + " (" + res.body.key + ") · custom" }, self.select);
          }
          self.select.value = res.body.key;
        } else if (res.status === 422 && res.body.detail && res.body.detail.problems) {
          self.setStatus("Workflow is invalid — fix and save again:", "err"); self.showProblems(res.body.detail.problems);
        } else {
          self.setStatus("Save failed (HTTP " + res.status + "): " + (typeof res.body.detail === "string" ? res.body.detail : JSON.stringify(res.body.detail || {})), "err");
        }
      }).catch(function (err) { self.setStatus("Save failed: " + err.message, "err"); });
  };

  Editor.prototype.deleteScheme = function () {
    var self = this, key = this.state.key;
    if (!key || this.custom.indexOf(key) < 0) { this.setStatus("Only saved custom workflows can be deleted.", "err"); return; }
    if (!confirm("Delete custom workflow '" + key + "'?")) return;
    fetch(this.api + "/schemes/" + encodeURIComponent(key), { method: "DELETE" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      self.schemes = self.schemes.filter(function (s) { return s.key !== key; });
      self.custom = self.custom.filter(function (k) { return k !== key; });
      Array.prototype.slice.call(self.select.options).forEach(function (o) { if (o.value === key) o.remove(); });
      self.setStatus("Deleted " + key, "ok");
      if (self.schemes.length) { self.select.value = self.schemes[0].key; self.load(self.schemes[0].key); }
    }).catch(function (err) { self.setStatus("Delete failed: " + err.message, "err"); });
  };

  Editor.prototype.exportBpmn = function () {
    if (!this.state.key || this.schemes.every(function (s) { return s.key !== this.state.key; }, this)) {
      this.setStatus("Save the workflow first, then export its BPMN.", "err"); return;
    }
    window.open(this.api + "/schemes/" + encodeURIComponent(this.state.key) + "/bpmn", "_blank");
  };

  window.ArcHubBpmnEditor = { mount: function (opts) { return new Editor(opts); } };
})();
