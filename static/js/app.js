const state = {
  datasets: [],
  dashboards: [],
  currentDataset: null,
  rows: [],
  charts: [],
  editingDashboardId: null,
};

const limits = {
  maxUploadMb: Number(document.body.dataset.maxUploadMb),
  maxDatasetRows: Number(document.body.dataset.maxDatasetRows),
  chartRowLimit: Number(document.body.dataset.chartRowLimit),
  maxCharts: Number(document.body.dataset.maxCharts),
  dashboardExports: document.body.dataset.dashboardExports === "true",
};

const elements = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  bindEvents();
  refreshWorkspace();
});

function cacheElements() {
  [
    "page-title", "db-status", "refresh-button", "upload-card", "file-input",
    "choose-file-button", "upload-progress", "dataset-select", "download-data-button",
    "delete-data-button", "dataset-workspace", "row-count", "column-count",
    "preview-count", "column-rules", "missing-strategy", "fill-value-field",
    "fill-value", "missing-columns", "remove-duplicates", "remove-empty",
    "cleaning-summary", "apply-cleaning-button", "preview-table", "dashboard-title",
    "builder-dataset-select", "chart-title", "chart-type", "x-column", "y-column",
    "y-column-field", "aggregation", "aggregation-field", "add-chart-button",
    "chart-count", "chart-grid", "print-dashboard-button", "save-dashboard-button",
    "saved-grid", "toast",
  ].forEach((id) => { elements[id] = document.getElementById(id); });
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  elements["choose-file-button"].addEventListener("click", () => elements["file-input"].click());
  elements["file-input"].addEventListener("change", () => uploadFile(elements["file-input"].files[0]));
  ["dragenter", "dragover"].forEach((eventName) => {
    elements["upload-card"].addEventListener(eventName, (event) => {
      event.preventDefault();
      elements["upload-card"].classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    elements["upload-card"].addEventListener(eventName, (event) => {
      event.preventDefault();
      elements["upload-card"].classList.remove("dragging");
    });
  });
  elements["upload-card"].addEventListener("drop", (event) => uploadFile(event.dataTransfer.files[0]));

  elements["dataset-select"].addEventListener("change", () => selectDataset(elements["dataset-select"].value));
  elements["builder-dataset-select"].addEventListener("change", () => loadBuilderDataset(elements["builder-dataset-select"].value, true));
  elements["missing-strategy"].addEventListener("change", toggleMissingValueField);
  elements["apply-cleaning-button"].addEventListener("click", applyCleaning);
  elements["download-data-button"].addEventListener("click", downloadCurrentDataset);
  elements["delete-data-button"].addEventListener("click", deleteCurrentDataset);
  elements["chart-type"].addEventListener("change", updateChartFieldVisibility);
  elements["add-chart-button"].addEventListener("click", addChart);
  elements["save-dashboard-button"].addEventListener("click", saveDashboard);
  elements["print-dashboard-button"].addEventListener("click", () => {
    if (!limits.dashboardExports) return window.location.assign("/pricing");
    window.print();
  });
  elements["refresh-button"].addEventListener("click", refreshWorkspace);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) throw new Error(payload.error || `Request failed with status ${response.status}.`);
  return payload;
}

async function refreshWorkspace() {
  elements["refresh-button"].disabled = true;
  try {
    await Promise.all([loadHealth(), loadDatasets(), loadDashboards()]);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    elements["refresh-button"].disabled = false;
  }
}

async function loadHealth() {
  try {
    const result = await api("/api/health");
    elements["db-status"].className = "db-status ok";
    elements["db-status"].innerHTML = "<span></span> Database connected";
    return result;
  } catch (error) {
    elements["db-status"].className = "db-status error";
    elements["db-status"].innerHTML = "<span></span> Database unavailable";
    throw error;
  }
}

async function loadDatasets() {
  const { datasets } = await api("/api/datasets");
  state.datasets = datasets;
  renderDatasetOptions();
  if (state.currentDataset && !datasets.some((item) => item.id === state.currentDataset.id)) {
    clearDatasetWorkspace();
  }
}

async function loadDashboards() {
  const { dashboards } = await api("/api/dashboards");
  state.dashboards = dashboards;
  renderSavedDashboards();
}

async function uploadFile(file) {
  if (!file) return;
  const extension = file.name.split(".").pop().toLowerCase();
  if (!["csv", "xls", "xlsx"].includes(extension)) {
    showToast("Choose a CSV, XLS, or XLSX file.", true);
    return;
  }
  if (file.size > limits.maxUploadMb * 1024 * 1024) {
    showToast(`File is too large. Maximum size is ${limits.maxUploadMb} MB.`, true);
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  setUploading(true);
  try {
    const result = await api("/api/datasets", { method: "POST", body: formData });
    state.currentDataset = result.dataset;
    state.rows = result.rows;
    await loadDatasets();
    elements["dataset-select"].value = result.dataset.id;
    renderDatasetWorkspace();
    showToast(`${result.dataset.name} uploaded successfully.`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setUploading(false);
    elements["file-input"].value = "";
  }
}

function setUploading(isUploading) {
  elements["upload-progress"].classList.toggle("hidden", !isUploading);
  elements["choose-file-button"].disabled = isUploading;
  elements["choose-file-button"].textContent = isUploading ? "Uploading…" : "Choose file";
}

function renderDatasetOptions() {
  const selectedData = state.currentDataset?.id || elements["dataset-select"].value;
  const selectedBuilder = elements["builder-dataset-select"].value;
  fillSelect(elements["dataset-select"], state.datasets, "Upload a dataset to begin");
  fillSelect(elements["builder-dataset-select"], state.datasets, "Select a dataset");
  if (state.datasets.some((item) => item.id === selectedData)) elements["dataset-select"].value = selectedData;
  if (state.datasets.some((item) => item.id === selectedBuilder)) elements["builder-dataset-select"].value = selectedBuilder;
}

function fillSelect(select, datasets, placeholder) {
  select.replaceChildren();
  select.append(new Option(placeholder, ""));
  datasets.forEach((dataset) => {
    select.append(new Option(`${dataset.name} · ${dataset.row_count.toLocaleString()} rows`, dataset.id));
  });
}

async function selectDataset(datasetId) {
  if (!datasetId) {
    clearDatasetWorkspace();
    return;
  }
  try {
    const result = await api(`/api/datasets/${datasetId}?limit=100`);
    state.currentDataset = result.dataset;
    state.rows = result.rows;
    renderDatasetWorkspace();
  } catch (error) {
    showToast(error.message, true);
  }
}

function clearDatasetWorkspace() {
  state.currentDataset = null;
  state.rows = [];
  elements["dataset-workspace"].classList.add("hidden");
  elements["download-data-button"].disabled = true;
  elements["delete-data-button"].disabled = true;
}

function renderDatasetWorkspace() {
  const dataset = state.currentDataset;
  if (!dataset) return clearDatasetWorkspace();
  elements["dataset-workspace"].classList.remove("hidden");
  elements["download-data-button"].disabled = false;
  elements["delete-data-button"].disabled = false;
  elements["row-count"].textContent = dataset.row_count.toLocaleString();
  elements["column-count"].textContent = dataset.columns.length.toLocaleString();
  elements["preview-count"].textContent = state.rows.length.toLocaleString();
  renderCleaningFields(dataset.columns);
  renderPreview(dataset.columns, state.rows);
}

function renderCleaningFields(columns) {
  elements["column-rules"].replaceChildren();
  elements["missing-columns"].replaceChildren();
  columns.forEach((column) => {
    const row = document.createElement("div");
    row.className = "column-rule";
    const input = document.createElement("input");
    input.type = "text";
    input.value = column;
    input.dataset.original = column;
    input.setAttribute("aria-label", `Rename ${column}`);
    const remove = document.createElement("label");
    remove.className = "remove-column";
    remove.title = `Remove ${column}`;
    remove.append(document.createTextNode("×"));
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.column = column;
    remove.append(checkbox);
    row.append(input, remove);
    elements["column-rules"].append(row);

    const missingOption = document.createElement("label");
    missingOption.className = "check-option";
    const missingCheckbox = document.createElement("input");
    missingCheckbox.type = "checkbox";
    missingCheckbox.value = column;
    missingCheckbox.checked = true;
    const label = document.createElement("span");
    label.textContent = column;
    missingOption.append(missingCheckbox, label);
    elements["missing-columns"].append(missingOption);
  });
  elements["missing-strategy"].value = "none";
  elements["fill-value"].value = "";
  elements["remove-duplicates"].checked = false;
  elements["remove-empty"].checked = true;
  toggleMissingValueField();
}

function renderPreview(columns, rows) {
  elements["preview-table"].replaceChildren();
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = column;
    headerRow.append(th);
  });
  head.append(headerRow);
  const body = document.createElement("tbody");
  rows.forEach((record) => {
    const row = document.createElement("tr");
    columns.forEach((column) => {
      const cell = document.createElement("td");
      const value = record[column];
      cell.textContent = value === null || value === undefined ? "—" : String(value);
      row.append(cell);
    });
    body.append(row);
  });
  elements["preview-table"].append(head, body);
}

function toggleMissingValueField() {
  elements["fill-value-field"].classList.toggle("hidden", elements["missing-strategy"].value !== "fill");
}

async function applyCleaning() {
  if (!state.currentDataset) return;
  const rename = {};
  const renamedLookup = {};
  document.querySelectorAll("#column-rules input[type='text']").forEach((input) => {
    const newName = input.value.trim();
    renamedLookup[input.dataset.original] = newName;
    if (input.dataset.original !== newName) rename[input.dataset.original] = newName;
  });
  const removeColumns = [...document.querySelectorAll(".remove-column input:checked")]
    .map((input) => renamedLookup[input.dataset.column]);
  const missingColumns = [...document.querySelectorAll("#missing-columns input:checked")]
    .map((input) => renamedLookup[input.value])
    .filter((column) => !removeColumns.includes(column));

  const payload = {
    rename,
    remove_columns: removeColumns,
    remove_duplicates: elements["remove-duplicates"].checked,
    remove_empty_rows: elements["remove-empty"].checked,
    missing: {
      strategy: elements["missing-strategy"].value,
      columns: missingColumns,
      value: elements["fill-value"].value,
    },
  };

  elements["apply-cleaning-button"].disabled = true;
  try {
    const result = await api(`/api/datasets/${state.currentDataset.id}/clean`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.currentDataset = result.dataset;
    state.rows = result.rows;
    state.charts = [];
    renderDatasetWorkspace();
    await loadDatasets();
    elements["dataset-select"].value = result.dataset.id;
    elements["cleaning-summary"].textContent = `${result.summary.rows_removed} rows and ${result.summary.columns_removed} columns removed.`;
    showToast("Cleaning rules applied.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    elements["apply-cleaning-button"].disabled = false;
  }
}

function downloadCurrentDataset() {
  if (state.currentDataset) window.location.assign(`/api/datasets/${state.currentDataset.id}/download`);
}

async function deleteCurrentDataset() {
  if (!state.currentDataset || !window.confirm(`Delete ${state.currentDataset.name} and its dashboards?`)) return;
  try {
    await api(`/api/datasets/${state.currentDataset.id}`, { method: "DELETE" });
    clearDatasetWorkspace();
    state.charts = [];
    await Promise.all([loadDatasets(), loadDashboards()]);
    showToast("Dataset deleted.");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function loadBuilderDataset(datasetId, resetCharts = false) {
  if (!datasetId) {
    state.currentDataset = null;
    state.rows = [];
    updateChartColumnOptions([]);
    return;
  }
  try {
    const result = await api(`/api/datasets/${datasetId}?limit=${limits.chartRowLimit}`);
    state.currentDataset = result.dataset;
    state.rows = result.rows;
    elements["dataset-select"].value = datasetId;
    if (resetCharts) {
      state.charts = [];
      state.editingDashboardId = null;
      renderCharts();
    }
    updateChartColumnOptions(result.dataset.columns);
    if (result.truncated) {
      showToast(`Charts use the first ${limits.chartRowLimit.toLocaleString()} rows of this dataset.`);
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

function updateChartColumnOptions(columns) {
  [elements["x-column"], elements["y-column"]].forEach((select, index) => {
    select.replaceChildren();
    select.append(new Option(index === 0 ? "Select a column" : "Count records", ""));
    columns.forEach((column) => select.append(new Option(column, column)));
  });
}

function updateChartFieldVisibility() {
  const histogram = elements["chart-type"].value === "histogram";
  elements["y-column-field"].classList.toggle("hidden", histogram);
  elements["aggregation-field"].classList.toggle("hidden", histogram);
}

function addChart() {
  if (!state.currentDataset) return showToast("Select a dataset first.", true);
  if (state.charts.length >= limits.maxCharts) {
    return showToast(`Your plan supports up to ${limits.maxCharts} charts per dashboard.`, true);
  }
  const type = elements["chart-type"].value;
  const x = elements["x-column"].value;
  const y = type === "histogram" ? null : elements["y-column"].value || null;
  const aggregation = type === "histogram" ? "none" : elements["aggregation"].value;
  if (!x) return showToast("Select an X-axis column.", true);
  if (type === "scatter" && !y) return showToast("Scatter plots require a Y-axis column.", true);
  if (["sum", "average"].includes(aggregation) && !y) return showToast("Sum and average require a Y-axis column.", true);
  if (["sum", "average"].includes(aggregation) && state.currentDataset.column_types[y] !== "number") {
    return showToast("Choose a numeric Y-axis column for sum or average.", true);
  }

  state.charts.push({
    id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
    title: elements["chart-title"].value.trim() || `${titleCase(type)} of ${x}`,
    type,
    x,
    y,
    aggregation,
  });
  elements["chart-title"].value = "";
  renderCharts();
}

function renderCharts() {
  elements["chart-grid"].replaceChildren();
  elements["chart-count"].textContent = `${state.charts.length} chart${state.charts.length === 1 ? "" : "s"}`;
  elements["save-dashboard-button"].disabled = state.charts.length === 0;
  elements["print-dashboard-button"].disabled = state.charts.length === 0;

  if (!state.charts.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<span>⌁</span><h3>Your charts will appear here</h3><p>Select a dataset and configure the first chart.</p>";
    elements["chart-grid"].append(empty);
    return;
  }

  state.charts.forEach((chart) => {
    const card = document.createElement("article");
    card.className = "chart-card";
    const controls = document.createElement("div");
    controls.className = "chart-card-controls";
    const remove = document.createElement("button");
    remove.className = "chart-remove";
    remove.type = "button";
    remove.title = "Remove chart";
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      state.charts = state.charts.filter((item) => item.id !== chart.id);
      renderCharts();
    });
    controls.append(remove);
    const plot = document.createElement("div");
    plot.className = "chart-plot";
    card.append(controls, plot);
    elements["chart-grid"].append(card);
    drawChart(plot, chart);
  });
}

function drawChart(container, chart) {
  if (typeof Plotly === "undefined") {
    container.textContent = "Chart library failed to load. Check your internet connection.";
    return;
  }
  const trace = buildTrace(chart, state.rows);
  Plotly.newPlot(container, [trace], {
    title: { text: chart.title, font: { family: "Manrope", size: 16, color: "#17213a" }, x: 0.04 },
    margin: { t: 62, r: 25, b: 60, l: 62 },
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#ffffff",
    colorway: ["#6d5dfc", "#1ab8a6", "#f4a261", "#df4f64", "#3b82f6"],
    xaxis: { gridcolor: "#edf0f5", automargin: true },
    yaxis: { gridcolor: "#edf0f5", automargin: true },
    font: { family: "DM Sans", color: "#5e6780" },
    showlegend: chart.type === "pie",
  }, {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
    toImageButtonOptions: { format: "png", filename: slugify(chart.title), scale: 2 },
  });
}

function buildTrace(chart, rows) {
  const validRows = rows.filter((row) => row[chart.x] !== null && row[chart.x] !== undefined);
  if (chart.type === "histogram") {
    return { type: "histogram", x: validRows.map((row) => row[chart.x]), marker: { color: "#6d5dfc" } };
  }

  let xValues;
  let yValues;
  const mustGroup = chart.aggregation !== "none" || (!chart.y && ["bar", "line", "area", "pie"].includes(chart.type));
  if (mustGroup) {
    const groups = new Map();
    validRows.forEach((row) => {
      const key = String(row[chart.x]);
      const current = groups.get(key) || { sum: 0, count: 0 };
      const numericValue = chart.y ? Number(row[chart.y]) : 1;
      if (Number.isFinite(numericValue)) current.sum += numericValue;
      current.count += 1;
      groups.set(key, current);
    });
    xValues = [...groups.keys()];
    yValues = [...groups.values()].map((group) => {
      if (chart.aggregation === "sum") return group.sum;
      if (chart.aggregation === "average") return group.count ? group.sum / group.count : 0;
      return group.count;
    });
  } else {
    xValues = validRows.map((row) => row[chart.x]);
    yValues = chart.y ? validRows.map((row) => row[chart.y]) : validRows.map(() => 1);
  }

  if (chart.type === "pie") return { type: "pie", labels: xValues, values: yValues, hole: .38 };
  if (chart.type === "scatter") return { type: "scatter", mode: "markers", x: xValues, y: yValues, marker: { color: "#6d5dfc", size: 8, opacity: .75 } };
  if (chart.type === "area") return { type: "scatter", mode: "lines", fill: "tozeroy", x: xValues, y: yValues, line: { color: "#6d5dfc", width: 3 } };
  if (chart.type === "line") return { type: "scatter", mode: "lines+markers", x: xValues, y: yValues, line: { color: "#6d5dfc", width: 3 } };
  return { type: "bar", x: xValues, y: yValues, marker: { color: "#6d5dfc" } };
}

async function saveDashboard() {
  const title = elements["dashboard-title"].value.trim();
  const datasetId = elements["builder-dataset-select"].value;
  if (!title) return showToast("Enter a dashboard title.", true);
  const payload = { title, dataset_id: datasetId, charts: state.charts };
  const updating = Boolean(state.editingDashboardId);
  try {
    const result = await api(updating ? `/api/dashboards/${state.editingDashboardId}` : "/api/dashboards", {
      method: updating ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.editingDashboardId = result.dashboard.id;
    await loadDashboards();
    showToast(updating ? "Dashboard updated." : "Dashboard saved.");
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderSavedDashboards() {
  elements["saved-grid"].replaceChildren();
  if (!state.dashboards.length) {
    const empty = document.createElement("div");
    empty.className = "empty-saved";
    empty.innerHTML = "<h3>No saved dashboards yet</h3><p>Build your first dashboard and it will appear here.</p>";
    elements["saved-grid"].append(empty);
    return;
  }
  state.dashboards.forEach((dashboard) => {
    const card = document.createElement("article");
    card.className = "saved-card";
    const icon = document.createElement("div");
    icon.className = "saved-card-icon";
    icon.textContent = "▦";
    const title = document.createElement("h3");
    title.textContent = dashboard.title;
    const meta = document.createElement("p");
    meta.textContent = `${dashboard.charts.length} charts · Updated ${formatDate(dashboard.updated_at)}`;
    const actions = document.createElement("div");
    actions.className = "saved-card-actions";
    const open = makeButton("Open", "button primary", () => openDashboard(dashboard.id));
    const exportButton = makeButton(
      limits.dashboardExports ? "Export JSON" : "Export JSON · Pro",
      "button tertiary",
      () => window.location.assign(limits.dashboardExports ? `/api/dashboards/${dashboard.id}/export` : "/pricing"),
    );
    const remove = makeButton("Delete", "button danger-ghost", () => removeDashboard(dashboard));
    actions.append(open, exportButton, remove);
    card.append(icon, title, meta, actions);
    elements["saved-grid"].append(card);
  });
}

async function openDashboard(dashboardId) {
  try {
    const { dashboard } = await api(`/api/dashboards/${dashboardId}`);
    state.editingDashboardId = dashboard.id;
    state.charts = dashboard.charts;
    elements["dashboard-title"].value = dashboard.title;
    elements["builder-dataset-select"].value = dashboard.dataset_id;
    await loadBuilderDataset(dashboard.dataset_id, false);
    renderCharts();
    switchView("builder-view");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function removeDashboard(dashboard) {
  if (!window.confirm(`Delete dashboard "${dashboard.title}"?`)) return;
  try {
    await api(`/api/dashboards/${dashboard.id}`, { method: "DELETE" });
    if (state.editingDashboardId === dashboard.id) state.editingDashboardId = null;
    await loadDashboards();
    showToast("Dashboard deleted.");
  } catch (error) {
    showToast(error.message, true);
  }
}

function makeButton(label, className, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function switchView(viewId) {
  const titles = {
    "data-view": "Prepare your data",
    "builder-view": "Build your dashboard",
    "saved-view": "Saved dashboards",
  };
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === viewId));
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === viewId));
  elements["page-title"].textContent = titles[viewId];
  if (viewId === "builder-view" && state.currentDataset) {
    elements["builder-dataset-select"].value = state.currentDataset.id;
    loadBuilderDataset(state.currentDataset.id, false);
  }
  if (viewId === "saved-view") loadDashboards().catch((error) => showToast(error.message, true));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

let toastTimer;
function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast show${isError ? " error" : ""}`;
  toastTimer = setTimeout(() => { elements.toast.className = "toast"; }, 3600);
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function slugify(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "chart";
}
