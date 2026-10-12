(() => {
  const state = { events: [], eventId: null, sceneId: null, tab: "overview", scenes: [], reports: [], summary: null, filter: "" };
  const $ = (selector, parent = document) => parent.querySelector(selector);
  const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
  const main = $("#mainView");
  const eventDialog = $("#eventDialog");
  const sceneDialog = $("#sceneDialog");
  const reviewDialog = $("#reviewDialog");
  let toastTimer;

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const fmt = (value) => new Intl.NumberFormat().format(value || 0);
  const dateLabel = (value) => value ? new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "Date not set";
  const byId = (id) => state.events.find((event) => event.id === id);
  const selectedEvent = () => byId(state.eventId);
  const selectedScene = () => state.scenes.find((scene) => scene.id === state.sceneId);
  const activeReports = () => state.sceneId ? state.reports.filter((report) => report.scene_id === state.sceneId) : state.reports;
  const activeSummary = () => state.summary || {};

  async function api(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
    });
    const type = response.headers.get("content-type") || "";
    const body = type.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) throw new Error(body?.error || `Request failed (${response.status})`);
    return body;
  }

  function toast(message) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 2700);
  }

  function showError(error) { toast(error?.message || "Something went wrong. Please try again."); }

  async function loadEvents() {
    state.events = await api("/api/events");
    renderSidebar();
  }

  async function refreshWorkspace() {
    const event = selectedEvent();
    if (!event) return renderHome();
    const sceneArg = state.sceneId ? `?scene_id=${encodeURIComponent(state.sceneId)}` : "";
    const [scenes, reports, summary] = await Promise.all([
      api(`/api/events/${event.id}/scenes`),
      api(`/api/events/${event.id}/reports`),
      api(`/api/events/${event.id}/summary${sceneArg}`),
    ]);
    state.scenes = scenes;
    state.reports = reports;
    state.summary = summary;
    renderSidebar();
    renderEvent();
  }

  function renderSidebar() {
    $("#eventCount").textContent = state.events.length;
    const host = $("#eventList");
    host.innerHTML = state.events.length ? state.events.map((event) => `
      <a class="event-link ${event.id === state.eventId ? "selected" : ""}" href="#event/${event.id}" data-action="open-event" data-id="${event.id}">
        <span class="event-bullet"></span><span class="event-link-main"><strong>${esc(event.name)}</strong><small>${esc(event.location || event.disaster_type || "New event")}</small></span>
      </a>`).join("") : `<div class="sidebar-empty">Your events will appear here.</div>`;
  }

  function renderHome() {
    state.eventId = null;
    state.sceneId = null;
    state.tab = "overview";
    renderSidebar();
    $("#breadcrumbCurrent").textContent = "EVENTS";
    if (!state.events.length) {
      main.innerHTML = `
        <section class="page-intro"><div><span class="eyebrow">YOUR FIELDWORK, ORGANIZED</span><h1>Make sense of the<br>damage, together.</h1><p>Create a disaster event to collect reports, organize affected areas into scenes, and turn field observations into clear, reviewable summaries.</p></div><div class="intro-actions"><button class="button button-dark" data-action="new-event">＋ Create first event <span>→</span></button></div></section>
        <div class="empty-state"><div class="empty-icon">⌁</div><h2>Your workspace is ready</h2><p>Start with an event, such as a regional flood or earthquake. Reports, scenes, exports, and charts will stay organized inside that event.</p><button class="button button-outline" data-action="new-event">Create an event</button></div>
        <div class="section-heading"><div><h2>Designed for clear reporting</h2><p>Every number traces back to submitted reports.</p></div></div>
        <div class="notice">TerraSignal extracts only details it can identify in the submitted text. Unclear quantities and missing severity stay blank for you to review.</div>`;
      return;
    }
    main.innerHTML = `
      <section class="page-intro"><div><span class="eyebrow">DISASTER RESPONSE WORKSPACE</span><h1>Events overview</h1><p>Keep each disaster event, affected scene, and reported impact together in one place.</p></div><div class="intro-actions"><button class="button button-dark" data-action="new-event">＋ New event <span>→</span></button></div></section>
      <div class="section-heading"><div><h2>Active and past events</h2><p>${state.events.length} ${state.events.length === 1 ? "event" : "events"} · Select an event to open its workspace</p></div></div>
      <div class="event-grid">${state.events.map((event) => eventCard(event)).join("")}</div>
      <div class="section-heading"><div><h2>Evidence over assumptions</h2><p>Keep reported impact transparent and easy to review.</p></div></div>
      <div class="notice">Quantities are grouped by their reported units so unlike measures are never added together. Dashboard totals describe reports submitted in TerraSignal, not verified physical damage or official economic loss.</div>`;
  }

  function eventCard(event) {
    const summary = event.summary || {};
    return `<article class="event-card" data-action="open-event" data-id="${event.id}" tabindex="0" role="button" aria-label="Open ${esc(event.name)}">
      <div class="event-card-top"><span class="event-type">${esc(event.disaster_type || "Disaster event")}</span>${recordMenu(event.name, `<button type="button" data-action="edit-event" data-id="${event.id}">Edit event</button><button type="button" class="record-menu-danger" data-action="delete-event" data-id="${event.id}">Delete event</button>`)}</div>
      <h3>${esc(event.name)}</h3><div class="event-location">⌖ ${esc(event.location || "Location not set")}</div>
      <div class="event-stats"><div class="event-stat"><strong>${fmt(summary.report_count)}</strong><span>reports</span></div><div class="event-stat"><strong>${fmt(summary.asset_mentions)}</strong><span>damage mentions</span></div><div class="event-stat"><strong>${fmt(event.scene_count)}</strong><span>scenes</span></div></div>
      <div class="event-card-foot"><span>${event.start_date ? dateLabel(event.start_date) : "Reporting period not set"}</span><span class="open-arrow">↗</span></div>
    </article>`;
  }

  function downloadLinks(eventId, sceneId = null) {
    const base = sceneId ? `/api/events/${eventId}/scenes/${sceneId}/export` : `/api/events/${eventId}/export`;
    return `<div class="download-menu"><a href="${base}?format=csv">↓ CSV</a><a href="${base}?format=json">↓ JSON</a></div>`;
  }

  function recordMenu(label, actions) {
    return `<details class="record-menu"><summary class="record-menu-trigger" aria-label="Actions for ${esc(label)}" title="Actions">···</summary><div class="record-menu-popover" role="group" aria-label="${esc(label)} actions">${actions}</div></details>`;
  }

  function eventActions(event) {
    return recordMenu(event.name, `<button type="button" data-action="edit-event" data-id="${event.id}">Edit event</button><button type="button" class="record-menu-danger" data-action="delete-event" data-id="${event.id}">Delete event</button>`);
  }

  function sceneActions(scene) {
    return recordMenu(scene.name, `<button type="button" data-action="edit-scene" data-id="${scene.id}">Edit scene</button><button type="button" class="record-menu-danger" data-action="delete-scene" data-id="${scene.id}">Delete scene</button>`);
  }

  function reportActions(report) {
    return recordMenu("report", `<button type="button" data-action="review-report" data-id="${report.id}">Review report</button><button type="button" class="record-menu-danger" data-action="delete-report" data-id="${report.id}">Delete report</button>`);
  }

  function renderEvent() {
    const event = selectedEvent();
    if (!event) return renderHome();
    const scene = selectedScene();
    $("#breadcrumbCurrent").textContent = `${event.name.toUpperCase()}${scene ? ` / ${scene.name.toUpperCase()}` : ""}`;
    const reports = activeReports();
    const summary = activeSummary();
    const sceneBanner = scene ? `<div class="scene-banner"><span>Viewing scene <strong>${esc(scene.name)}</strong>${scene.location ? ` · ${esc(scene.location)}` : ""}</span><button data-action="clear-scene">← Show entire event</button></div>` : "";
    const tabs = `<nav class="tabs" aria-label="Event sections">
      <button class="tab-button ${state.tab === "overview" ? "active" : ""}" data-action="tab" data-tab="overview">Overview</button>
      <button class="tab-button ${state.tab === "reports" ? "active" : ""}" data-action="tab" data-tab="reports">Reports <span class="tab-badge">${fmt(reports.length)}</span></button>
      <button class="tab-button ${state.tab === "scenes" ? "active" : ""}" data-action="tab" data-tab="scenes">Scenes <span class="tab-badge">${fmt(state.scenes.length)}</span></button>
    </nav>`;
    main.innerHTML = `
      <section class="event-header"><div class="event-heading"><button class="back-link" data-action="home">← All events</button><div class="eyebrow">EVENT WORKSPACE</div><h1>${esc(event.name)}</h1><div class="event-heading-meta"><span class="event-type">${esc(event.disaster_type || "Disaster event")}</span><span class="dot">·</span><span>${esc(event.location || "Location not set")}</span>${event.start_date ? `<span class="dot">·</span><span>${dateLabel(event.start_date)}</span>` : ""}</div>${event.description ? `<p class="event-description">${esc(event.description)}</p>` : ""}</div>
        <div class="header-actions">${eventActions(event)}${downloadLinks(event.id)}</div>
      </section>
      ${tabs}${sceneBanner}${state.tab === "overview" ? overviewMarkup(event, summary) : state.tab === "reports" ? reportsMarkup(event, reports) : scenesMarkup(event)}
    `;
  }

  function metricCard(label, value, note, icon) {
    return `<div class="metric-card"><div class="metric-label">${label}<span class="metric-icon">${icon}</span></div><strong class="metric-value">${value}</strong><div class="metric-foot">${note}</div></div>`;
  }

  function overviewMarkup(event, summary) {
    const category = summary.category_mentions || {};
    const locations = summary.location_mentions || {};
    const severities = summary.severity_mentions || {};
    const quantities = summary.quantity_totals || {};
    const qtyText = Object.values(quantities).reduce((count, units) => count + Object.keys(units).length, 0);
    const breakdown = Object.entries(quantities).flatMap(([name, units]) => Object.entries(units).map(([unit, amount]) => `${fmt(amount)} ${unit} ${name.toLowerCase()}`));
    const sceneCards = state.scenes.length ? `<div class="scene-strip">${state.scenes.slice(0, 3).map(sceneCard).join("")}</div>` : `<div class="empty-state"><div class="empty-icon">⌖</div><h2>Add your first scene</h2><p>Organize reports by district, affected area, incident, or reporting period.</p><button class="button button-outline" data-action="new-scene">＋ Create a scene</button></div>`;
    return `
      <div class="metric-grid">${metricCard("Submitted reports", fmt(summary.report_count), "In this event or selected scene", "▤")}${metricCard("Damage mentions", fmt(summary.asset_mentions), "Extracted from submitted reports", "⌁")}${metricCard("Categories affected", fmt(summary.categories_affected), "Distinct infrastructure categories", "◫")}${metricCard("With quantities", fmt(summary.quantified_mentions), qtyText ? `${qtyText} category and unit combinations` : "No quantities extracted yet", "#")}</div>
      <div class="chart-grid"><section class="chart-card"><h3>Damage mentions by category</h3><p class="chart-sub">Each mention comes from a submitted report</p><div id="categoryChart" class="bar-chart"></div></section><section class="chart-card"><h3>Reported damage mix</h3><p class="chart-sub">Share of extracted damage mentions</p><div id="categoryDonut"></div></section></div>
      <div class="location-grid"><section class="chart-card"><h3>Damage mentions by reported location</h3><p class="chart-sub">Asset mentions grouped by extracted place, then scene or event location</p><div id="locationChart" class="bar-chart"></div></section><section class="chart-card"><h3>Reported severity</h3><p class="chart-sub">Only explicit severity terms are included</p><div class="severity-list">${Object.entries(severities).length ? Object.entries(severities).map(([name, count]) => `<span class="severity-pill">${esc(name)} <strong>${fmt(count)}</strong></span>`).join("") : `<span class="no-chart-data">No severity information identified.</span>`}</div><div class="section-heading" style="margin:20px 0 9px"><div><h3>Quantities by reported unit</h3><p class="chart-sub">Different units are not combined</p></div></div><div class="severity-list">${breakdown.length ? breakdown.map((line) => `<span class="severity-pill">${esc(line)}</span>`).join("") : `<span class="no-chart-data">No explicit quantities identified.</span>`}</div></section></div>
      <div class="section-heading"><div><h2>Scenes</h2><p>Open an area to see its reports and statistics</p></div><button class="text-link" data-action="tab" data-tab="scenes">Manage scenes →</button></div>${sceneCards}
      <div class="section-heading"><div><h2>Recent reports</h2><p>${reportsForSummaryText(summary.report_count)} in this view</p></div><button class="text-link" data-action="tab" data-tab="reports">View reports →</button></div>${recentReportsMarkup(activeReports().slice(0, 3))}
      <div class="section-heading"><div><h2>Interpretation note</h2><p>How to read this dashboard</p></div></div><div class="notice">These figures summarize reported damage, not verified physical damage or an official loss assessment. Quantities with different units are kept separate to avoid misleading totals. Review the extracted details before sharing or relying on a summary.</div>`;
  }

  function reportsForSummaryText(count) { return `${fmt(count)} ${count === 1 ? "report" : "reports"}`; }

  function drawBars(elementId, obj, emptyText = "No report data for this view yet.") {
    const element = $(`#${elementId}`);
    if (!element) return;
    const entries = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);
    if (!entries.length) { element.innerHTML = `<div class="no-chart-data">${emptyText}</div>`; return; }
    const max = Math.max(...entries.map((entry) => Number(entry[1]) || 0), 1);
    element.innerHTML = entries.map(([label, value]) => `<div class="bar-row" title="${esc(label)}: ${fmt(value)}"><span class="bar-label">${esc(label)}</span><span class="bar-track"><span class="bar-fill" style="width:${Math.max(3, Math.round(Number(value) / max * 100))}%"></span></span><strong class="bar-value">${fmt(value)}</strong></div>`).join("");
  }

  function drawDonut(elementId, obj) {
    const element = $(`#${elementId}`);
    if (!element) return;
    const entries = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);
    const total = entries.reduce((sum, row) => sum + Number(row[1]), 0);
    if (!total) { element.innerHTML = `<div class="no-chart-data">No damage mentions to chart yet.</div>`; return; }
    const colors = ["#397e73", "#d58a62", "#7299a9", "#c4aa63", "#8894b8", "#86aa8c"];
    let cursor = 0;
    const stops = entries.map(([, value], index) => {
      const start = cursor;
      cursor += Number(value) / total * 100;
      return `${colors[index % colors.length]} ${start}% ${cursor}%`;
    }).join(", ");
    element.innerHTML = `<div class="donut-wrap"><div class="donut" style="background:conic-gradient(${stops})"><div class="donut-center"><strong>${fmt(total)}</strong><small>mentions</small></div></div><div class="legend">${entries.slice(0, 6).map(([name, value], index) => `<div class="legend-item"><i class="legend-dot" style="background:${colors[index % colors.length]}"></i><span>${esc(name)}</span><strong>${Math.round(Number(value) / total * 100)}%</strong></div>`).join("")}</div></div>`;
  }

  function sceneCard(scene) {
    const summary = scene.summary || {};
    return `<article class="scene-card" data-action="open-scene" data-id="${scene.id}" tabindex="0" role="button"><div class="scene-card-head"><h4>${esc(scene.name)}</h4>${sceneActions(scene)}</div><div class="scene-location">⌖ ${esc(scene.location || "Location not set")}</div><div class="scene-counts"><div><strong>${fmt(summary.report_count)}</strong><small>reports</small></div><div><strong>${fmt(summary.asset_mentions)}</strong><small>mentions</small></div></div></article>`;
  }

  function scenesMarkup(event) {
    return `<div class="scene-toolbar"><div><div class="eyebrow">EVENT AREAS</div><h2 style="font:600 18px Manrope,sans-serif;margin:0">Scenes in ${esc(event.name)}</h2><p class="chart-sub">A scene can represent a district, affected area, incident, or reporting period.</p></div><button class="button button-dark" data-action="new-scene">＋ New scene</button></div>
    ${state.scenes.length ? `<div class="scene-list">${state.scenes.map((scene) => `<article class="scene-row"><div class="scene-row-main"><div class="scene-row-title"><span class="event-bullet"></span><h3>${esc(scene.name)}</h3></div><p>${esc(scene.description || "No scene description")}</p><div class="scene-row-meta">⌖ ${esc(scene.location || "Location not set")} · ${fmt(scene.summary?.report_count)} ${scene.summary?.report_count === 1 ? "report" : "reports"} · ${fmt(scene.summary?.asset_mentions)} damage mentions</div></div><div class="scene-row-actions"><button class="button button-outline button-small" data-action="open-scene" data-id="${scene.id}">Open scene →</button>${downloadLinks(event.id, scene.id)}${sceneActions(scene)}</div></article>`).join("")}</div>` : `<div class="empty-state"><div class="empty-icon">⌖</div><h2>No scenes yet</h2><p>Create a scene to keep reports for an affected area separate while still including them in the event-wide dashboard.</p><button class="button button-outline" data-action="new-scene">Create a scene</button></div>`}
    <div class="section-heading"><div><h2>Event-level data</h2><p>Downloads include every report in this event, across all scenes and event-wide reports.</p></div>${downloadLinks(event.id)}</div>`;
  }

  function reportsMarkup(event, reports) {
    const options = [`<option value="">Event-wide report</option>`, ...state.scenes.map((scene) => `<option value="${scene.id}" ${scene.id === state.sceneId ? "selected" : ""}>${esc(scene.name)}</option>`)].join("");
    return `<div class="report-layout"><section class="panel-card report-form-card"><span class="eyebrow">NEW FIELD REPORT</span><h3>Describe what was affected</h3><p class="chart-sub">Use ordinary language. Keep quantities, units, locations, and severity explicit when known.</p><form id="reportForm"><label>Assign to scene<select name="scene_id">${options}</select></label><label>Damage report<textarea name="text" required maxlength="5000" placeholder="Example: Heavy flooding in Village A damaged 25 houses, two bridges, and approximately 3 km of road. The water supply system is partially damaged."></textarea></label><p class="form-note">Extraction is rules-based and explainable. Missing details remain blank. You can review and correct every assessment after submitting.</p><button class="button button-dark submit-report" type="submit">Process report <span>→</span></button><div id="reportFormError"></div></form></section>
      <section class="report-list-panel"><div class="report-list-head"><div><h3>${state.sceneId ? `Reports · ${esc(selectedScene()?.name || "Scene")}` : "All event reports"}</h3><span class="report-count">${reports.length} ${reports.length === 1 ? "record" : "records"}</span></div><div class="filter-row"><input type="search" id="reportSearch" placeholder="Search reports…" value="${esc(state.filter)}" aria-label="Search reports"></div></div><div id="reportRows" class="report-list">${reportCards(reports)}</div></section></div>`;
  }

  function reportCards(reports) {
    const query = state.filter.trim().toLowerCase();
    const filtered = query ? reports.filter((report) => `${report.original_text} ${report.extracted?.location || ""} ${(report.extracted?.damages || []).map((damage) => `${damage.asset} ${damage.category}`).join(" ")}`.toLowerCase().includes(query)) : reports;
    if (!filtered.length) return `<div class="report-empty">${reports.length ? "No reports match your search." : "No reports submitted yet. Add the first report for this event."}</div>`;
    return filtered.map((report) => {
      const chips = (report.extracted?.damages || []).map((damage) => `<span class="damage-chip"><em>${esc(damage.quantity == null ? "Quantity unknown" : `${fmt(damage.quantity)} ${damage.unit || "items"}`)}</em> ${esc(damage.asset)} · ${esc(damage.category)}${damage.severity ? ` · ${esc(damage.severity)}` : ""}</span>`).join("");
      const date = report.created_at ? new Date(report.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "Recently";
      return `<article class="report-card"><div class="report-card-top"><div class="report-card-meta"><span class="badge">${esc(report.scene_name || "Event-wide")}</span><span>${esc(report.extracted?.location || report.scene_location || eventLocationFallback(report) || "Location unknown")}</span><span>· ${esc(date)}</span></div><div class="report-card-actions">${reportActions(report)}</div></div><p class="report-text">${esc(report.original_text)}</p><div class="damage-chips">${chips || `<span class="damage-chip">No infrastructure mention identified · Review manually</span>`}</div></article>`;
    }).join("");
  }

  function eventLocationFallback(report) { return report.event_location || ""; }

  function recentReportsMarkup(reports) {
    return reports.length ? `<div class="report-list">${reports.map((report) => `<article class="report-card"><div class="report-card-top"><div class="report-card-meta"><span class="badge">${esc(report.scene_name || "Event-wide")}</span><span>${esc(report.extracted?.location || report.scene_location || report.event_location || "Location unknown")}</span></div><div class="report-card-actions">${reportActions(report)}</div></div><p class="report-text">${esc(report.original_text)}</p><div class="damage-chips">${(report.extracted?.damages || []).slice(0, 4).map((damage) => `<span class="damage-chip"><em>${damage.quantity == null ? "Qty unknown" : `${fmt(damage.quantity)} ${esc(damage.unit || "items")}`}</em> ${esc(damage.asset)}</span>`).join("") || `<span class="damage-chip">No damage mentions extracted</span>`}</div></article>`).join("")}</div>` : `<div class="report-empty">No reports in this view yet. Submit a report to start the dashboard.</div>`;
  }

  function showEventDialog(event = null) {
    const form = $("#eventForm");
    form.reset();
    form.elements.id.value = event?.id || "";
    form.elements.name.value = event?.name || "";
    form.elements.disaster_type.value = event?.disaster_type || "";
    form.elements.location.value = event?.location || "";
    form.elements.description.value = event?.description || "";
    form.elements.start_date.value = event?.start_date || "";
    form.elements.end_date.value = event?.end_date || "";
    $("#eventDialogTitle").textContent = event ? "Edit event" : "Create an event";
    $("#eventSaveButton").innerHTML = event ? "Save changes <span>→</span>" : "Create event <span>→</span>";
    eventDialog.showModal();
  }

  function showSceneDialog(scene = null) {
    const form = $("#sceneForm");
    form.reset();
    form.elements.id.value = scene?.id || "";
    form.elements.name.value = scene?.name || "";
    form.elements.location.value = scene?.location || "";
    form.elements.description.value = scene?.description || "";
    $("#sceneDialogTitle").textContent = scene ? "Edit scene" : "Create a scene";
    sceneDialog.showModal();
  }

  function damageEditorRow(damage = {}) {
    const categories = ["Residential buildings", "Roads & transport", "Bridges", "Power & electricity", "Water & sanitation", "Public facilities", "Other infrastructure"];
    const categoryOptions = categories.map((category) => `<option ${category === damage.category ? "selected" : ""}>${esc(category)}</option>`).join("");
    const severityOptions = ["", "Minor", "Moderate", "Severe"].map((severity) => `<option value="${severity}" ${severity === (damage.severity || "") ? "selected" : ""}>${severity || "Unspecified"}</option>`).join("");
    return `<div class="damage-edit-row"><label>Asset<input data-field="asset" value="${esc(damage.asset || "")}" placeholder="asset"></label><label>Category<select data-field="category">${categoryOptions}</select></label><label>Quantity<input data-field="quantity" type="number" min="0" step="any" value="${damage.quantity == null ? "" : esc(damage.quantity)}" placeholder="—"></label><label>Unit<input data-field="unit" value="${esc(damage.unit || "items")}" placeholder="items"></label><label>Severity<select data-field="severity">${severityOptions}</select></label><button type="button" class="remove-damage" aria-label="Remove damage mention">×</button><label style="grid-column:1/-2">Condition<input data-field="condition" value="${esc(damage.condition || "")}" placeholder="Explicitly stated condition"></label></div>`;
  }

  function showReviewDialog(report) {
    const form = $("#reviewForm");
    form.reset();
    form.elements.id.value = report.id;
    form.elements.location.value = report.extracted?.location || "";
    form.elements.disaster_type.value = report.extracted?.disaster_type || "";
    $("#reviewOriginal").textContent = report.original_text;
    const damages = report.extracted?.damages || [];
    $("#damageEditor").innerHTML = damages.length ? damages.map(damageEditorRow).join("") : damageEditorRow({ category: "Other infrastructure", asset: "", unit: "items" });
    reviewDialog.showModal();
  }

  async function openEvent(id, sceneId = null, tab = "overview") {
    state.eventId = id;
    state.sceneId = sceneId;
    state.tab = tab;
    state.filter = "";
    await loadEvents();
    await refreshWorkspace();
  }

  document.addEventListener("click", async (event) => {
    const actionEl = event.target.closest("[data-action]");
    if (!actionEl) return;
    const action = actionEl.dataset.action;
    const id = actionEl.dataset.id;
    try {
      if (action === "new-event") return showEventDialog();
      if (action === "home") return renderHome();
      if (action === "open-event") {
        if (event.target.closest("button, .record-menu")) return;
        return await openEvent(id);
      }
      if (action === "edit-event") {
        event.stopPropagation();
        return showEventDialog(byId(id));
      }
      if (action === "delete-event") {
        const row = byId(id);
        const reports = row?.summary?.report_count || 0;
        const scenes = row?.scene_count || 0;
        if (!window.confirm(`Delete “${row?.name}” and permanently remove ${reports} reports and ${scenes} scenes? This cannot be undone.`)) return;
        await api(`/api/events/${id}`, { method: "DELETE" });
        state.eventId = null;
        state.sceneId = null;
        await loadEvents();
        renderHome();
        return toast("Event and its data deleted.");
      }
      if (action === "tab") {
        state.tab = actionEl.dataset.tab;
        if (state.tab === "reports") state.filter = "";
        return renderEvent();
      }
      if (action === "clear-scene") {
        state.sceneId = null;
        await refreshWorkspace();
        return;
      }
      if (action === "open-scene") {
        if (event.target.closest(".record-menu")) return;
        state.sceneId = id;
        state.tab = "overview";
        await refreshWorkspace();
        return;
      }
      if (action === "new-scene") return showSceneDialog();
      if (action === "edit-scene") return showSceneDialog(state.scenes.find((scene) => scene.id === id));
      if (action === "delete-scene") {
        const scene = state.scenes.find((row) => row.id === id);
        const count = scene?.summary?.report_count || 0;
        if (!window.confirm(`Delete “${scene?.name}” and permanently remove its ${count} reports? This cannot be undone.`)) return;
        await api(`/api/events/${state.eventId}/scenes/${id}`, { method: "DELETE" });
        if (state.sceneId === id) state.sceneId = null;
        await loadEvents(); await refreshWorkspace();
        return toast("Scene and its reports deleted.");
      }
      if (action === "review-report") {
        const report = state.reports.find((row) => row.id === id);
        if (report) showReviewDialog(report);
        return;
      }
      if (action === "delete-report") {
        if (!window.confirm("Delete this report and its extracted assessment?")) return;
        await api(`/api/events/${state.eventId}/reports/${id}`, { method: "DELETE" });
        await loadEvents(); await refreshWorkspace();
        return toast("Report deleted.");
      }
    } catch (error) { showError(error); }
  });

  $("#sideAddEvent").addEventListener("click", () => showEventDialog());
  $("#topAddEvent").addEventListener("click", () => showEventDialog());
  $("#eventsNav").addEventListener("click", () => renderHome());
  $(".brand").addEventListener("click", (event) => { event.preventDefault(); renderHome(); });
  $$('[data-close]').forEach((button) => button.addEventListener("click", () => document.getElementById(button.dataset.close).close()));

  $("#eventForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form).entries());
    const id = values.id;
    delete values.id;
    try {
      const result = id ? await api(`/api/events/${id}`, { method: "PATCH", body: JSON.stringify(values) }) : await api("/api/events", { method: "POST", body: JSON.stringify(values) });
      eventDialog.close();
      await loadEvents();
      if (!id) {
        state.eventId = result.id;
        state.sceneId = null;
        state.tab = "overview";
      }
      await refreshWorkspace();
      toast(id ? "Event details saved." : "Event created.");
    } catch (error) { showError(error); }
  });

  $("#sceneForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form).entries());
    const id = values.id;
    delete values.id;
    try {
      await api(id ? `/api/events/${state.eventId}/scenes/${id}` : `/api/events/${state.eventId}/scenes`, { method: id ? "PATCH" : "POST", body: JSON.stringify(values) });
      sceneDialog.close();
      await loadEvents(); await refreshWorkspace();
      toast(id ? "Scene details saved." : "Scene created.");
    } catch (error) { showError(error); }
  });

  main.addEventListener("submit", async (event) => {
    if (event.target.id !== "reportForm") return;
    event.preventDefault();
    const form = event.target;
    const submit = $(".submit-report", form);
    const errorHost = $("#reportFormError", form);
    const values = Object.fromEntries(new FormData(form).entries());
    submit.disabled = true;
    submit.textContent = "Processing…";
    errorHost.innerHTML = "";
    try {
      await api(`/api/events/${state.eventId}/reports`, { method: "POST", body: JSON.stringify(values) });
      await loadEvents(); await refreshWorkspace();
      toast("Report processed. Review the extracted details.");
    } catch (error) {
      errorHost.innerHTML = `<div class="form-error">${esc(error.message)}</div>`;
      submit.disabled = false;
      submit.innerHTML = "Process report <span>→</span>";
    }
  });

  $("#reviewForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const id = form.elements.id.value;
    const damages = $$(".damage-edit-row", $("#damageEditor")).map((row) => ({
      asset: $("[data-field='asset']", row).value.trim() || "asset",
      category: $("[data-field='category']", row).value,
      quantity: $("[data-field='quantity']", row).value,
      unit: $("[data-field='unit']", row).value.trim() || "items",
      severity: $("[data-field='severity']", row).value,
      condition: $("[data-field='condition']", row).value.trim(),
      detail: "",
    }));
    const extracted = { location: form.elements.location.value, disaster_type: form.elements.disaster_type.value, damages };
    try {
      await api(`/api/events/${state.eventId}/reports/${id}`, { method: "PATCH", body: JSON.stringify({ extracted }) });
      reviewDialog.close();
      await loadEvents(); await refreshWorkspace();
      toast("Assessment updated.");
    } catch (error) { showError(error); }
  });

  $("#addDamage").addEventListener("click", () => { $("#damageEditor").insertAdjacentHTML("beforeend", damageEditorRow({ category: "Other infrastructure", asset: "", unit: "items" })); });
  $("#damageEditor").addEventListener("click", (event) => { if (event.target.closest(".remove-damage")) event.target.closest(".damage-edit-row").remove(); });

  main.addEventListener("input", (event) => {
    if (event.target.id !== "reportSearch") return;
    state.filter = event.target.value;
    const rows = $("#reportRows");
    if (rows) rows.innerHTML = reportCards(activeReports());
  });
  main.addEventListener("submit", (event) => { if (event.target.id === "reportForm") return; });

  const initialRender = async () => {
    try {
      await loadEvents();
      const hash = location.hash.match(/^#event\/([\w-]+)$/);
      if (hash && byId(hash[1])) await openEvent(hash[1]);
      else renderHome();
    } catch (error) {
      main.innerHTML = `<div class="empty-state"><h2>Workspace unavailable</h2><p>${esc(error.message)}</p><button class="button button-outline" onclick="location.reload()">Try again</button></div>`;
    }
  };

  main.addEventListener("keydown", (event) => {
    if ((event.key === "Enter" || event.key === " ") && event.target.matches(".event-card[role='button'], .scene-card[role='button']")) event.target.click();
  });

  const renderHook = new MutationObserver(() => {
    if (!$("#categoryChart")) return;
    const summary = activeSummary();
    drawBars("categoryChart", summary.category_mentions);
    drawDonut("categoryDonut", summary.category_mentions);
    drawBars("locationChart", summary.location_mentions, "No location data available for this view.");
  });
  renderHook.observe(main, { childList: true });
  initialRender();
})();
