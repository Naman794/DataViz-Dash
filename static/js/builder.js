const builderState = {
  datasets: [],
  dashboards: [],
  dataset: null,
  rows: [],
  rowsTruncated: false,
  charts: [],
  editingDashboardId: document.body.dataset.initialDashboardId || null,
  selectedChartId: null,
  selectedField: null,
  visualType: "bar",
  canvasZoom: 1,
  canvasViewMode: "fit-page",
  gridVisible: true,
  inspectorTab: "build",
};

const builderLimits = {
  chartRows: Number(document.body.dataset.chartRowLimit),
  maxCharts: Number(document.body.dataset.maxCharts),
  exports: document.body.dataset.dashboardExports === "true",
};

const builderElements = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheBuilderElements();
  bindBuilderEvents();
  refreshBuilder();
});

function cacheBuilderElements() {
  [
    "builder-db-status", "builder-dashboard-title", "builder-page-dataset",
    "builder-save-state", "builder-new-button", "builder-print-button",
    "builder-save-button", "builder-field-count", "builder-field-search",
    "builder-field-list", "builder-field-profile", "builder-saved-count",
    "builder-saved-list", "builder-canvas-description", "builder-visual-count",
    "builder-workbench", "builder-toggle-properties", "builder-focus-canvas",
    "builder-view-canvas", "builder-view-data", "builder-view-saved",
    "builder-saved-drawer", "builder-close-saved", "builder-inspector-tabs",
    "builder-toggle-grid", "builder-fit-page", "builder-fit-width",
    "builder-actual-size", "builder-zoom-out", "builder-zoom-in",
    "builder-zoom-label", "builder-canvas-viewport", "builder-page-shell",
    "builder-dashboard-page",
    "builder-analysis-grid", "builder-properties-title", "builder-visual-types",
    "builder-visual-title", "builder-x-label", "builder-x-column",
    "builder-date-group-field", "builder-date-group",
    "builder-y-field", "builder-y-column", "builder-aggregation-field",
    "builder-aggregation", "builder-sort-field", "builder-sort",
    "builder-top-field", "builder-top-n", "builder-visual-size",
    "builder-add-visual", "builder-cancel-edit", "builder-toast",
  ].forEach((id) => { builderElements[id] = document.getElementById(id); });
}

function bindBuilderEvents() {
  builderElements["builder-page-dataset"].addEventListener("change", changeDataset);
  builderElements["builder-field-search"].addEventListener("input", renderFields);
  builderElements["builder-toggle-properties"].addEventListener("click", toggleBuilderPanel);
  builderElements["builder-focus-canvas"].addEventListener("click", toggleCanvasFocus);
  document.querySelectorAll("[data-builder-view]").forEach((button) => {
    button.addEventListener("click", () => handleBuilderView(button.dataset.builderView));
  });
  builderElements["builder-close-saved"].addEventListener("click", closeSavedDrawer);
  builderElements["builder-inspector-tabs"].addEventListener("click", (event) => {
    const button = event.target.closest("[data-inspector-tab]");
    if (button) switchInspectorTab(button.dataset.inspectorTab);
  });
  builderElements["builder-toggle-grid"].addEventListener("click", () => setGridVisible(!builderState.gridVisible));
  builderElements["builder-fit-page"].addEventListener("click", () => fitCanvas("fit-page"));
  builderElements["builder-fit-width"].addEventListener("click", () => fitCanvas("fit-width"));
  builderElements["builder-actual-size"].addEventListener("click", () => setCanvasZoom(1, "actual"));
  builderElements["builder-zoom-out"].addEventListener("click", () => adjustCanvasZoom(-.1));
  builderElements["builder-zoom-in"].addEventListener("click", () => adjustCanvasZoom(.1));
  builderElements["builder-visual-types"].addEventListener("click", (event) => {
    const button = event.target.closest("[data-visual-type]");
    if (button) setVisualType(button.dataset.visualType);
  });
  builderElements["builder-add-visual"].addEventListener("click", saveVisual);
  builderElements["builder-cancel-edit"].addEventListener("click", resetVisualForm);
  builderElements["builder-save-button"].addEventListener("click", saveDashboard);
  builderElements["builder-new-button"].addEventListener("click", newDashboard);
  builderElements["builder-print-button"].addEventListener("click", () => {
    if (!builderLimits.exports) return window.location.assign("/pricing");
    window.print();
  });
  builderElements["builder-dashboard-title"].addEventListener("input", markUnsaved);
  restoreBuilderLayout();
  window.addEventListener("resize", () => {
    if (["fit-page", "fit-width"].includes(builderState.canvasViewMode)) fitCanvas(builderState.canvasViewMode);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (builderElements["builder-saved-drawer"].classList.contains("open")) closeSavedDrawer();
    else if (document.body.classList.contains("canvas-focus")) toggleCanvasFocus();
  });
}

function restoreBuilderLayout() {
  let layout = {};
  try {
    layout = JSON.parse(sessionStorage.getItem("dataviz-builder-layout") || "{}");
  } catch (error) {
    layout = {};
  }
  builderElements["builder-workbench"].classList.toggle("properties-collapsed", Boolean(layout.propertiesCollapsed));
  builderState.inspectorTab = layout.inspectorTab || "build";
  builderState.gridVisible = layout.gridVisible !== false;
  updateBuilderLayoutControls();
  switchInspectorTab(builderState.inspectorTab, false);
  setGridVisible(builderState.gridVisible, false);
  window.requestAnimationFrame(() => fitCanvas("fit-page"));
}

function saveBuilderLayout() {
  const layout = {
    propertiesCollapsed: builderElements["builder-workbench"].classList.contains("properties-collapsed"),
    inspectorTab: builderState.inspectorTab,
    gridVisible: builderState.gridVisible,
  };
  try {
    sessionStorage.setItem("dataviz-builder-layout", JSON.stringify(layout));
  } catch (error) {
    // The layout still works when browser storage is unavailable.
  }
}

function toggleBuilderPanel() {
  builderElements["builder-workbench"].classList.toggle("properties-collapsed");
  saveBuilderLayout();
  updateBuilderLayoutControls();
  resizeCanvasPlots();
  window.setTimeout(() => fitCanvas(builderState.canvasViewMode), 220);
}

function updateBuilderLayoutControls() {
  const propertiesCollapsed = builderElements["builder-workbench"].classList.contains("properties-collapsed");
  const propertiesButton = builderElements["builder-toggle-properties"];
  propertiesButton.textContent = propertiesCollapsed ? "‹" : "›";
  propertiesButton.setAttribute("aria-expanded", String(!propertiesCollapsed));
  propertiesButton.setAttribute("aria-label", `${propertiesCollapsed ? "Expand" : "Collapse"} inspector`);
}

function handleBuilderView(view) {
  document.querySelectorAll("[data-builder-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.builderView === view);
  });
  if (view === "saved") {
    builderElements["builder-saved-drawer"].classList.add("open");
    builderElements["builder-saved-drawer"].setAttribute("aria-hidden", "false");
    return;
  }
  closeSavedDrawer(false);
  if (view === "data") {
    if (builderElements["builder-workbench"].classList.contains("properties-collapsed")) toggleBuilderPanel();
    switchInspectorTab("data");
  } else if (view === "canvas") {
    switchInspectorTab("build");
  }
}

function closeSavedDrawer(resetView = true) {
  builderElements["builder-saved-drawer"].classList.remove("open");
  builderElements["builder-saved-drawer"].setAttribute("aria-hidden", "true");
  if (resetView) handleBuilderView("canvas");
}

function switchInspectorTab(tab, persist = true) {
  builderState.inspectorTab = tab;
  document.querySelectorAll("[data-inspector-tab]").forEach((button) => {
    const active = button.dataset.inspectorTab === tab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-inspector-panel]").forEach((panel) => {
    const active = panel.dataset.inspectorPanel === tab;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
  if (persist) saveBuilderLayout();
}

function setGridVisible(visible, persist = true) {
  builderState.gridVisible = visible;
  builderElements["builder-dashboard-page"].classList.toggle("show-grid", visible);
  builderElements["builder-toggle-grid"].setAttribute("aria-pressed", String(visible));
  if (persist) saveBuilderLayout();
}

function fitCanvas(mode) {
  const viewport = builderElements["builder-canvas-viewport"];
  if (!viewport.clientWidth || !viewport.clientHeight) return;
  const widthScale = Math.max(.35, (viewport.clientWidth - 56) / 1280);
  const heightScale = Math.max(.35, (viewport.clientHeight - 56) / 720);
  setCanvasZoom(mode === "fit-width" ? widthScale : Math.min(widthScale, heightScale), mode);
}

function adjustCanvasZoom(delta) {
  setCanvasZoom(builderState.canvasZoom + delta, "custom");
}

function setCanvasZoom(value, mode = "custom") {
  builderState.canvasZoom = Math.min(1.5, Math.max(.35, Math.round(value * 20) / 20));
  builderState.canvasViewMode = mode;
  builderElements["builder-page-shell"].style.setProperty("--canvas-scale", builderState.canvasZoom);
  builderElements["builder-zoom-label"].textContent = `${Math.round(builderState.canvasZoom * 100)}%`;
  syncPageShellSize();
  resizeCanvasPlots();
}

function syncPageShellSize() {
  const pageHeight = Math.max(720, builderElements["builder-dashboard-page"].scrollHeight);
  builderElements["builder-page-shell"].style.width = `${1280 * builderState.canvasZoom}px`;
  builderElements["builder-page-shell"].style.height = `${pageHeight * builderState.canvasZoom}px`;
}

function toggleCanvasFocus() {
  const focused = document.body.classList.toggle("canvas-focus");
  const button = builderElements["builder-focus-canvas"];
  button.textContent = focused ? "Exit focus" : "Focus canvas";
  button.setAttribute("aria-pressed", String(focused));
  resizeCanvasPlots();
  window.setTimeout(() => fitCanvas("fit-page"), 30);
}

function resizeCanvasPlots() {
  window.setTimeout(() => {
    if (!window.Plotly?.Plots) return;
    document.querySelectorAll(".js-plotly-plot").forEach((plot) => window.Plotly.Plots.resize(plot));
  }, 220);
}

async function builderApi(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) throw new Error(payload.error || `Request failed with status ${response.status}.`);
  return payload;
}

async function refreshBuilder() {
  try {
    await Promise.all([loadBuilderHealth(), loadBuilderDatasets(), loadSavedDashboards()]);
    if (builderState.editingDashboardId) {
      await openSavedDashboard(builderState.editingDashboardId, false);
    }
  } catch (error) {
    showBuilderToast(error.message, true);
  }
}

async function loadBuilderHealth() {
  const status = builderElements["builder-db-status"];
  try {
    await builderApi("/api/health");
    status.className = "db-status ok";
    status.innerHTML = "<span></span> Database connected";
  } catch (error) {
    status.className = "db-status error";
    status.innerHTML = "<span></span> Database unavailable";
    throw error;
  }
}

async function loadBuilderDatasets() {
  const { datasets } = await builderApi("/api/datasets");
  builderState.datasets = datasets;
  const select = builderElements["builder-page-dataset"];
  select.replaceChildren(new Option("Choose a prepared dataset", ""));
  datasets.forEach((dataset) => {
    select.append(new Option(`${dataset.name} · ${dataset.row_count.toLocaleString()} rows`, dataset.id));
  });
}

async function changeDataset(event) {
  const datasetId = event.target.value;
  if (builderState.charts.length && builderState.dataset?.id !== datasetId) {
    const confirmed = window.confirm("Changing the dataset will clear the visuals on this canvas. Continue?");
    if (!confirmed) {
      event.target.value = builderState.dataset?.id || "";
      return;
    }
    builderState.charts = [];
    builderState.editingDashboardId = null;
    resetVisualForm();
  }
  if (!datasetId) {
    clearBuilderDataset();
    return;
  }
  try {
    await loadBuilderDataset(datasetId);
    renderVisuals();
    markUnsaved();
  } catch (error) {
    showBuilderToast(error.message, true);
  }
}

async function loadBuilderDataset(datasetId) {
  const result = await builderApi(`/api/datasets/${datasetId}?limit=${builderLimits.chartRows}`);
  builderState.dataset = result.dataset;
  builderState.rows = result.rows;
  builderState.rowsTruncated = result.truncated;
  builderElements["builder-page-dataset"].value = datasetId;
  populateFieldSelects();
  renderFields();
  renderFieldProfile(null);
  updateCanvasDescription();
  builderElements["builder-save-button"].disabled = builderState.charts.length === 0;
}

function clearBuilderDataset() {
  builderState.dataset = null;
  builderState.rows = [];
  builderState.rowsTruncated = false;
  builderState.selectedField = null;
  builderElements["builder-field-count"].textContent = "0";
  builderElements["builder-field-list"].innerHTML = '<p class="rail-empty">Choose a dataset to inspect its fields.</p>';
  renderFieldProfile(null);
  populateFieldSelects();
  updateCanvasDescription();
  renderVisuals();
}

function populateFieldSelects() {
  const columns = builderState.dataset?.columns || [];
  const x = builderElements["builder-x-column"];
  const y = builderElements["builder-y-column"];
  const previousX = x.value;
  const previousY = y.value;
  x.replaceChildren(new Option("Select a field", ""));
  y.replaceChildren(new Option("Count records", ""));
  columns.forEach((column) => {
    x.append(new Option(column, column));
    y.append(new Option(column, column));
  });
  if (columns.includes(previousX)) x.value = previousX;
  if (columns.includes(previousY)) y.value = previousY;
}

function updateCanvasDescription() {
  if (!builderState.dataset) {
    builderElements["builder-canvas-description"].textContent = "Select a dataset, then add your first visual.";
    return;
  }
  builderElements["builder-canvas-description"].textContent = builderState.rowsTruncated
    ? `Using the first ${builderLimits.chartRows.toLocaleString()} rows allowed by your plan.`
    : `${builderState.dataset.row_count.toLocaleString()} source rows.`;
}

function isMissingValue(value) {
  return value === null || value === undefined || (typeof value === "string" && value.trim() === "");
}

function parseDashboardDate(value) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value;
  if (typeof value !== "string") return null;
  const cleaned = value.trim();
  if (!cleaned) return null;
  const timestamp = /^\d{4}-\d{2}-\d{2}$/.test(cleaned)
    ? Date.parse(`${cleaned}T00:00:00Z`)
    : Date.parse(cleaned);
  return Number.isNaN(timestamp) ? null : new Date(timestamp);
}

function groupDashboardDate(value, grouping) {
  const parsed = parseDashboardDate(value);
  if (!parsed) return null;
  const year = parsed.getUTCFullYear();
  const month = parsed.getUTCMonth() + 1;
  if (grouping === "year") return String(year);
  if (grouping === "quarter") return `${year} Q${Math.ceil(month / 3)}`;
  return `${year}-${String(month).padStart(2, "0")}`;
}

function renderFields() {
  const container = builderElements["builder-field-list"];
  const columns = builderState.dataset?.columns || [];
  const query = builderElements["builder-field-search"].value.trim().toLowerCase();
  const matches = columns.filter((column) => column.toLowerCase().includes(query));
  builderElements["builder-field-count"].textContent = columns.length.toLocaleString();
  container.replaceChildren();
  if (!matches.length) {
    const empty = document.createElement("p");
    empty.className = "rail-empty";
    empty.textContent = columns.length ? "No fields match that search." : "Choose a dataset to inspect its fields.";
    container.append(empty);
    return;
  }
  matches.forEach((column) => {
    const type = builderState.dataset.column_types[column] || "text";
    const button = document.createElement("button");
    button.type = "button";
    button.className = `field-button${builderState.selectedField === column ? " active" : ""}`;
    const icon = document.createElement("span");
    icon.className = "field-icon";
    icon.textContent = type === "number" ? "123" : "Aa";
    const name = document.createElement("strong");
    name.textContent = column;
    const label = document.createElement("small");
    label.textContent = type;
    button.append(icon, name, label);
    button.addEventListener("click", () => {
      builderState.selectedField = column;
      if (!builderElements["builder-x-column"].value) builderElements["builder-x-column"].value = column;
      renderFields();
      renderFieldProfile(column);
    });
    container.append(button);
  });
}

function renderFieldProfile(column) {
  const panel = builderElements["builder-field-profile"];
  const heading = '<div class="rail-heading"><div><span class="rail-kicker">PROFILE</span><h2>Field summary</h2></div></div>';
  if (!column || !builderState.dataset) {
    panel.innerHTML = `${heading}<p class="rail-empty">Select a field to see its quality and statistics.</p>`;
    return;
  }
  const values = builderState.rows.map((row) => row[column]);
  const present = values.filter((value) => value !== null && value !== undefined && value !== "");
  const unique = new Set(present.map((value) => String(value))).size;
  const numeric = present.map(Number).filter(Number.isFinite);
  const type = builderState.dataset.column_types[column] || "text";
  const statistics = [
    ["Type", type],
    ["Missing", (values.length - present.length).toLocaleString()],
    ["Unique", unique.toLocaleString()],
    ["Samples", values.length.toLocaleString()],
  ];
  if (numeric.length) {
    statistics.push(
      ["Average", formatMetric(numeric.reduce((sum, value) => sum + value, 0) / numeric.length)],
      ["Minimum", formatMetric(numeric.reduce((minimum, value) => Math.min(minimum, value), numeric[0]))],
      ["Maximum", formatMetric(numeric.reduce((maximum, value) => Math.max(maximum, value), numeric[0]))],
    );
  }
  panel.innerHTML = heading;
  const title = document.createElement("h3");
  title.className = "profile-name";
  title.textContent = column;
  const grid = document.createElement("div");
  grid.className = "profile-grid";
  statistics.forEach(([label, value]) => {
    const item = document.createElement("div");
    const key = document.createElement("span");
    key.textContent = label;
    const content = document.createElement("strong");
    content.textContent = value;
    item.append(key, content);
    grid.append(item);
  });
  panel.append(title, grid);
  if (builderState.rowsTruncated) {
    const note = document.createElement("p");
    note.className = "profile-note";
    note.textContent = `Profile uses the first ${builderLimits.chartRows.toLocaleString()} rows.`;
    panel.append(note);
  }
}

function setVisualType(type) {
  builderState.visualType = type;
  document.querySelectorAll("[data-visual-type]").forEach((button) => {
    button.classList.toggle("active", button.dataset.visualType === type);
  });
  const histogram = type === "histogram";
  const table = type === "table";
  const kpi = type === "kpi";
  const supportsDateGrouping = ["area", "bar", "line", "pie"].includes(type);
  builderElements["builder-y-field"].classList.toggle("hidden", histogram);
  builderElements["builder-aggregation-field"].classList.toggle("hidden", histogram || table);
  builderElements["builder-sort-field"].classList.toggle("hidden", histogram || table || kpi);
  builderElements["builder-top-field"].classList.toggle("hidden", histogram || kpi);
  builderElements["builder-date-group-field"].classList.toggle("hidden", !supportsDateGrouping);
  if (!supportsDateGrouping) builderElements["builder-date-group"].value = "none";
  builderElements["builder-x-label"].textContent = table ? "First table column" : (kpi ? "Count / label field" : "Category / X-axis");
  if (kpi && builderElements["builder-aggregation"].value === "none") {
    builderElements["builder-aggregation"].value = "count";
  }
}

function saveVisual() {
  if (!builderState.dataset) return showBuilderToast("Choose a prepared dataset first.", true);
  const editing = builderState.charts.find((chart) => chart.id === builderState.selectedChartId);
  if (!editing && builderState.charts.length >= builderLimits.maxCharts) {
    return showBuilderToast(`Your plan supports up to ${builderLimits.maxCharts} visuals.`, true);
  }
  const type = builderState.visualType;
  const x = builderElements["builder-x-column"].value;
  const y = type === "histogram" ? null : builderElements["builder-y-column"].value || null;
  const aggregation = type === "histogram" || type === "table" ? "none" : builderElements["builder-aggregation"].value;
  const dateGroup = builderElements["builder-date-group"].value;
  if (!x) return showBuilderToast("Select a field for this visual.", true);
  if (type === "scatter" && !y) return showBuilderToast("Scatter plots require a Y-axis field.", true);
  if (["sum", "average", "minimum", "maximum"].includes(aggregation)) {
    if (!y) return showBuilderToast("Choose a value field for this aggregation.", true);
    if (builderState.dataset.column_types[y] !== "number") {
      return showBuilderToast("Choose a numeric value field for this aggregation.", true);
    }
  }
  if (dateGroup !== "none") {
    const hasDate = builderState.rows.some((row) => parseDashboardDate(row[x]));
    if (!hasDate) return showBuilderToast("Date grouping requires a field containing valid dates.", true);
  }
  const chart = {
    id: editing?.id || (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`),
    title: builderElements["builder-visual-title"].value.trim() || defaultVisualTitle(type, x),
    type,
    x,
    y,
    aggregation,
    sort: builderElements["builder-sort"].value,
    top_n: Number(builderElements["builder-top-n"].value),
    size: builderElements["builder-visual-size"].value,
    date_group: dateGroup,
  };
  if (editing) {
    builderState.charts = builderState.charts.map((item) => item.id === chart.id ? chart : item);
  } else {
    builderState.charts.push(chart);
  }
  resetVisualForm();
  renderVisuals();
  markUnsaved();
}

function renderVisuals() {
  const grid = builderElements["builder-analysis-grid"];
  grid.replaceChildren();
  builderElements["builder-visual-count"].textContent = `${builderState.charts.length} visual${builderState.charts.length === 1 ? "" : "s"}`;
  builderElements["builder-save-button"].disabled = !builderState.dataset || builderState.charts.length === 0;
  builderElements["builder-print-button"].disabled = builderState.charts.length === 0;
  if (!builderState.charts.length) {
    const empty = document.createElement("div");
    empty.className = "analysis-empty";
    empty.innerHTML = "<span>⌁</span><h2>Build your first visual</h2><p>Select a dataset, then choose a chart, KPI, or table.</p>";
    const actions = document.createElement("div");
    actions.className = "analysis-empty-actions";
    const datasetButton = smallButton("Select dataset", "Select a dataset", () => builderElements["builder-page-dataset"].focus());
    datasetButton.className = "button secondary compact";
    const visualButton = smallButton("Add visual", "Configure a visual", () => {
      if (!builderState.dataset) {
        builderElements["builder-page-dataset"].focus();
        return showBuilderToast("Choose a dataset first.", true);
      }
      if (builderElements["builder-workbench"].classList.contains("properties-collapsed")) {
        toggleBuilderPanel();
      }
      switchInspectorTab("build");
      builderElements["builder-x-column"].focus();
    });
    visualButton.className = "button primary compact";
    actions.append(datasetButton, visualButton);
    empty.append(actions);
    grid.append(empty);
    window.requestAnimationFrame(syncPageShellSize);
    return;
  }
  builderState.charts.forEach((chart) => {
    const card = document.createElement("article");
    card.className = `analysis-card ${chart.size || "half"}${builderState.selectedChartId === chart.id ? " selected" : ""}`;
    card.dataset.chartId = chart.id;
    card.addEventListener("dragstart", (event) => {
      card.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", chart.id);
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
      document.querySelectorAll(".analysis-card").forEach((item) => item.classList.remove("drop-target"));
    });
    card.addEventListener("dragover", (event) => {
      event.preventDefault();
      card.classList.add("drop-target");
    });
    card.addEventListener("dragleave", () => card.classList.remove("drop-target"));
    card.addEventListener("drop", (event) => {
      event.preventDefault();
      const source = document.querySelector(".analysis-card.dragging");
      if (source && source.dataset.chartId !== chart.id) reorderVisuals(source.dataset.chartId, chart.id);
    });
    card.addEventListener("click", (event) => {
      if (!event.target.closest("button")) editVisual(chart.id);
    });
    card.append(makeVisualToolbar(chart));
    if (chart.type === "kpi") renderKpi(card, chart);
    else if (chart.type === "table") renderDataTable(card, chart);
    else renderPlot(card, chart);
    grid.append(card);
  });
  window.requestAnimationFrame(syncPageShellSize);
}

function makeVisualToolbar(chart) {
  const toolbar = document.createElement("div");
  toolbar.className = "visual-toolbar";
  const drag = smallButton("⋮⋮", "Drag to reorder", () => {});
  drag.draggable = true;
  drag.className = "visual-drag-handle";
  const edit = smallButton("✎", "Edit visual", () => editVisual(chart.id));
  const resize = smallButton("↔", `Make visual ${chart.size === "full" ? "half" : "full"} width`, () => toggleVisualWidth(chart.id));
  const duplicate = smallButton("⧉", "Duplicate visual", () => duplicateVisual(chart));
  const remove = smallButton("×", "Remove visual", () => {
    builderState.charts = builderState.charts.filter((item) => item.id !== chart.id);
    if (builderState.selectedChartId === chart.id) resetVisualForm();
    renderVisuals();
    markUnsaved();
  });
  toolbar.append(drag, edit, resize, duplicate, remove);
  return toolbar;
}

function reorderVisuals(sourceId, targetId) {
  const sourceIndex = builderState.charts.findIndex((chart) => chart.id === sourceId);
  const targetIndex = builderState.charts.findIndex((chart) => chart.id === targetId);
  if (sourceIndex < 0 || targetIndex < 0) return;
  const [chart] = builderState.charts.splice(sourceIndex, 1);
  builderState.charts.splice(targetIndex, 0, chart);
  renderVisuals();
  markUnsaved();
}

function toggleVisualWidth(chartId) {
  builderState.charts = builderState.charts.map((chart) => (
    chart.id === chartId ? { ...chart, size: chart.size === "full" ? "half" : "full" } : chart
  ));
  renderVisuals();
  markUnsaved();
}

function smallButton(label, title, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.title = title;
  button.setAttribute("aria-label", title);
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function duplicateVisual(chart) {
  if (builderState.charts.length >= builderLimits.maxCharts) {
    return showBuilderToast(`Your plan supports up to ${builderLimits.maxCharts} visuals.`, true);
  }
  builderState.charts.push({ ...chart, id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`, title: `${chart.title} copy` });
  renderVisuals();
  markUnsaved();
}

function renderPlot(card, chart) {
  const plot = document.createElement("div");
  plot.className = "analysis-plot";
  card.append(plot);
  if (typeof Plotly === "undefined") {
    plot.textContent = "Chart library failed to load. Check your internet connection.";
    return;
  }
  const trace = buildBuilderTrace(chart);
  Plotly.react(plot, [trace], {
    title: { text: chart.title, font: { family: "Manrope", size: 16, color: "#111315" }, x: .04 },
    margin: { t: 58, r: 24, b: 54, l: 56 },
    paper_bgcolor: "#fff",
    plot_bgcolor: "#fff",
    colorway: ["#0f766e", "#111315", "#d99132", "#39738c", "#8a5a44"],
    xaxis: { gridcolor: "#e8ece9", automargin: true },
    yaxis: { gridcolor: "#e8ece9", automargin: true },
    font: { family: "DM Sans", color: "#667078" },
    showlegend: chart.type === "pie",
  }, {
    responsive: true,
    displaylogo: false,
    toImageButtonOptions: { format: "png", filename: slugifyBuilder(chart.title), scale: 2 },
  });
}

function buildBuilderTrace(chart) {
  const validRows = builderState.rows.filter((row) => !isMissingValue(row[chart.x]));
  if (chart.type === "histogram") {
    return { type: "histogram", x: validRows.map((row) => row[chart.x]), marker: { color: "#0f766e" } };
  }
  let points;
  const grouped = chart.aggregation !== "none" || (chart.date_group || "none") !== "none" || (!chart.y && ["bar", "line", "area", "pie"].includes(chart.type));
  if (grouped) {
    const groups = new Map();
    validRows.forEach((row) => {
      const key = chart.date_group && chart.date_group !== "none"
        ? groupDashboardDate(row[chart.x], chart.date_group)
        : String(row[chart.x]);
      if (key === null) return;
      const group = groups.get(key) || { values: [], count: 0 };
      const numeric = chart.y ? Number(row[chart.y]) : 1;
      if (Number.isFinite(numeric)) group.values.push(numeric);
      group.count += 1;
      groups.set(key, group);
    });
    points = [...groups].map(([x, group]) => ({ x, y: aggregateValues(group, chart.aggregation) }));
  } else {
    points = validRows.map((row) => ({ x: row[chart.x], y: chart.y ? row[chart.y] : 1 }));
  }
  if (chart.date_group && chart.date_group !== "none" && chart.sort === "default") {
    points.sort((first, second) => String(first.x).localeCompare(String(second.x)));
  }
  if (chart.sort === "ascending") points.sort((a, b) => Number(a.y) - Number(b.y));
  if (chart.sort === "descending" || (chart.top_n && chart.sort === "default")) points.sort((a, b) => Number(b.y) - Number(a.y));
  if (chart.top_n) points = points.slice(0, chart.top_n);
  const x = points.map((point) => point.x);
  const y = points.map((point) => point.y);
  if (chart.type === "pie") return { type: "pie", labels: x, values: y, hole: .38 };
  if (chart.type === "scatter") return { type: "scatter", mode: "markers", x, y, marker: { color: "#0f766e", size: 8, opacity: .78 } };
  if (chart.type === "area") return { type: "scatter", mode: "lines", fill: "tozeroy", x, y, line: { color: "#0f766e", width: 3 } };
  if (chart.type === "line") return { type: "scatter", mode: "lines+markers", x, y, line: { color: "#0f766e", width: 3 } };
  return { type: "bar", x, y, marker: { color: "#0f766e" } };
}

function aggregateValues(group, aggregation) {
  if (aggregation === "count" || aggregation === "none") return group.count;
  if (!group.values.length) return 0;
  if (aggregation === "sum") return group.values.reduce((sum, value) => sum + value, 0);
  if (aggregation === "average") return group.values.reduce((sum, value) => sum + value, 0) / group.values.length;
  if (aggregation === "minimum") return group.values.reduce((minimum, value) => Math.min(minimum, value), group.values[0]);
  if (aggregation === "maximum") return group.values.reduce((maximum, value) => Math.max(maximum, value), group.values[0]);
  return group.count;
}

function renderKpi(card, chart) {
  const visual = document.createElement("div");
  visual.className = "kpi-visual";
  const label = document.createElement("span");
  label.textContent = chart.title;
  const value = document.createElement("strong");
  const field = chart.y || chart.x;
  const values = builderState.rows.map((row) => row[field]).filter((item) => !isMissingValue(item));
  const numeric = values.map(Number).filter(Number.isFinite);
  let metric = values.length;
  if (chart.aggregation === "sum") metric = numeric.reduce((sum, item) => sum + item, 0);
  if (chart.aggregation === "average") metric = numeric.length ? numeric.reduce((sum, item) => sum + item, 0) / numeric.length : 0;
  if (chart.aggregation === "minimum") metric = numeric.length ? numeric.reduce((minimum, item) => Math.min(minimum, item), numeric[0]) : 0;
  if (chart.aggregation === "maximum") metric = numeric.length ? numeric.reduce((maximum, item) => Math.max(maximum, item), numeric[0]) : 0;
  value.textContent = formatMetric(metric);
  visual.append(label, value);
  card.append(visual);
}

function renderDataTable(card, chart) {
  const wrapper = document.createElement("div");
  wrapper.className = "analysis-table-wrap";
  const table = document.createElement("table");
  const caption = document.createElement("caption");
  caption.textContent = chart.title;
  const columns = [...new Set([chart.x, chart.y].filter(Boolean))];
  const head = document.createElement("thead");
  const headingRow = document.createElement("tr");
  columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.textContent = column;
    headingRow.append(cell);
  });
  head.append(headingRow);
  const body = document.createElement("tbody");
  builderState.rows.slice(0, chart.top_n || 20).forEach((row) => {
    const tableRow = document.createElement("tr");
    columns.forEach((column) => {
      const cell = document.createElement("td");
      cell.textContent = row[column] ?? "";
      tableRow.append(cell);
    });
    body.append(tableRow);
  });
  table.append(caption, head, body);
  wrapper.append(table);
  card.append(wrapper);
}

function editVisual(chartId) {
  const chart = builderState.charts.find((item) => item.id === chartId);
  if (!chart) return;
  builderState.selectedChartId = chart.id;
  if (builderElements["builder-workbench"].classList.contains("properties-collapsed")) toggleBuilderPanel();
  switchInspectorTab("build");
  setVisualType(chart.type);
  builderElements["builder-visual-title"].value = chart.title;
  builderElements["builder-x-column"].value = chart.x;
  builderElements["builder-y-column"].value = chart.y || "";
  builderElements["builder-aggregation"].value = chart.aggregation || "none";
  builderElements["builder-sort"].value = chart.sort || "default";
  builderElements["builder-top-n"].value = String(chart.top_n || 0);
  builderElements["builder-visual-size"].value = chart.size || "half";
  builderElements["builder-date-group"].value = chart.date_group || "none";
  builderElements["builder-properties-title"].textContent = "Edit visual";
  builderElements["builder-add-visual"].textContent = "Update visual";
  builderElements["builder-cancel-edit"].classList.remove("hidden");
  renderVisuals();
}

function resetVisualForm() {
  builderState.selectedChartId = null;
  builderElements["builder-visual-title"].value = "";
  builderElements["builder-x-column"].value = "";
  builderElements["builder-y-column"].value = "";
  builderElements["builder-aggregation"].value = "count";
  builderElements["builder-sort"].value = "default";
  builderElements["builder-top-n"].value = "0";
  builderElements["builder-visual-size"].value = "half";
  builderElements["builder-date-group"].value = "none";
  builderElements["builder-properties-title"].textContent = "Add a visual";
  builderElements["builder-add-visual"].textContent = "＋ Add visual";
  builderElements["builder-cancel-edit"].classList.add("hidden");
  setVisualType("bar");
  renderVisuals();
}

async function saveDashboard() {
  const title = builderElements["builder-dashboard-title"].value.trim();
  if (!title) return showBuilderToast("Enter a dashboard title.", true);
  if (!builderState.dataset || !builderState.charts.length) return showBuilderToast("Add at least one visual before saving.", true);
  const payload = {
    title,
    dataset_id: builderState.dataset.id,
    charts: builderState.charts,
    filters: [],
  };
  const updating = Boolean(builderState.editingDashboardId);
  try {
    const result = await builderApi(updating ? `/api/dashboards/${builderState.editingDashboardId}` : "/api/dashboards", {
      method: updating ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    builderState.editingDashboardId = result.dashboard.id;
    builderState.charts = result.dashboard.charts;
    window.history.replaceState({}, "", `/builder/${result.dashboard.id}`);
    await loadSavedDashboards();
    builderElements["builder-save-state"].textContent = "Saved just now";
    showBuilderToast(updating ? "Dashboard updated." : "Dashboard saved.");
    renderVisuals();
  } catch (error) {
    showBuilderToast(error.message, true);
  }
}

async function loadSavedDashboards() {
  const { dashboards } = await builderApi("/api/dashboards");
  builderState.dashboards = dashboards;
  const container = builderElements["builder-saved-list"];
  builderElements["builder-saved-count"].textContent = dashboards.length.toLocaleString();
  container.replaceChildren();
  if (!dashboards.length) {
    const empty = document.createElement("p");
    empty.className = "rail-empty";
    empty.textContent = "No saved dashboards yet.";
    container.append(empty);
    return;
  }
  dashboards.forEach((dashboard) => {
    const item = document.createElement("div");
    item.className = "builder-saved-item";
    const details = document.createElement("div");
    const link = document.createElement("a");
    link.href = `/builder/${dashboard.id}`;
    link.textContent = dashboard.title;
    const meta = document.createElement("small");
    meta.textContent = `${dashboard.charts.length} visuals · ${formatBuilderDate(dashboard.updated_at)}`;
    details.append(link, meta);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "saved-delete";
    remove.title = "Delete dashboard";
    remove.textContent = "×";
    remove.addEventListener("click", () => deleteSavedDashboard(dashboard));
    item.append(details, remove);
    container.append(item);
  });
}

async function openSavedDashboard(dashboardId, updateUrl = true) {
  const { dashboard } = await builderApi(`/api/dashboards/${dashboardId}`);
  builderState.editingDashboardId = dashboard.id;
  builderState.charts = dashboard.charts;
  builderElements["builder-dashboard-title"].value = dashboard.title;
  await loadBuilderDataset(dashboard.dataset_id);
  if (updateUrl) window.history.replaceState({}, "", `/builder/${dashboard.id}`);
  builderElements["builder-save-state"].textContent = `Saved ${formatBuilderDate(dashboard.updated_at)}`;
  renderVisuals();
}

async function deleteSavedDashboard(dashboard) {
  if (!window.confirm(`Delete dashboard "${dashboard.title}"?`)) return;
  try {
    await builderApi(`/api/dashboards/${dashboard.id}`, { method: "DELETE" });
    if (builderState.editingDashboardId === dashboard.id) newDashboard();
    await loadSavedDashboards();
    showBuilderToast("Dashboard deleted.");
  } catch (error) {
    showBuilderToast(error.message, true);
  }
}

function newDashboard() {
  builderState.editingDashboardId = null;
  builderState.charts = [];
  builderElements["builder-dashboard-title"].value = "Untitled dashboard";
  builderElements["builder-save-state"].textContent = "Not saved";
  window.history.replaceState({}, "", "/builder");
  resetVisualForm();
}

function markUnsaved() {
  builderElements["builder-save-state"].textContent = "Unsaved changes";
}

function defaultVisualTitle(type, field) {
  if (type === "kpi") return `Summary of ${field}`;
  if (type === "table") return `Table of ${field}`;
  return `${type.charAt(0).toUpperCase() + type.slice(1)} of ${field}`;
}

function formatMetric(value) {
  if (!Number.isFinite(Number(value))) return String(value);
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, notation: Math.abs(value) >= 1_000_000 ? "compact" : "standard" }).format(value);
}

function formatBuilderDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function slugifyBuilder(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "visual";
}

let builderToastTimer;
function showBuilderToast(message, isError = false) {
  clearTimeout(builderToastTimer);
  const toast = builderElements["builder-toast"];
  toast.textContent = message;
  toast.className = `toast show${isError ? " error" : ""}`;
  builderToastTimer = setTimeout(() => { toast.className = "toast"; }, 3600);
}
