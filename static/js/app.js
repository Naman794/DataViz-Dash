const state = {
  datasets: [],
  currentDataset: null,
  rows: [],
};

const limits = {
  maxUploadMb: Number(document.body.dataset.maxUploadMb),
  maxDatasetRows: Number(document.body.dataset.maxDatasetRows),
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
    "choose-file-button", "sample-data-button", "upload-progress", "google-sheet-form",
    "google-sheet-url", "connect-google-sheet-button", "dataset-select", "refresh-sheet-button", "download-data-button",
    "delete-data-button", "dataset-workspace", "row-count", "column-count",
    "preview-count", "column-rules", "missing-strategy", "fill-value-field",
    "fill-value", "missing-columns", "remove-duplicates", "remove-empty",
    "cleaning-summary", "apply-cleaning-button", "preview-table", "dataset-source-status", "toast",
  ].forEach((id) => { elements[id] = document.getElementById(id); });
}

function bindEvents() {
  elements["choose-file-button"].addEventListener("click", () => elements["file-input"].click());
  elements["sample-data-button"].addEventListener("click", openSampleDashboard);
  elements["file-input"].addEventListener("change", () => uploadFile(elements["file-input"].files[0]));
  elements["google-sheet-form"].addEventListener("submit", connectGoogleSheet);
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
  elements["missing-strategy"].addEventListener("change", toggleMissingValueField);
  elements["apply-cleaning-button"].addEventListener("click", applyCleaning);
  elements["download-data-button"].addEventListener("click", downloadCurrentDataset);
  elements["refresh-sheet-button"].addEventListener("click", refreshCurrentSheet);
  elements["delete-data-button"].addEventListener("click", deleteCurrentDataset);
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
    await Promise.all([loadHealth(), loadDatasets()]);
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

async function connectGoogleSheet(event) {
  event.preventDefault();
  const url = elements["google-sheet-url"].value.trim();
  if (!url) return;
  setSheetConnecting(true);
  try {
    const result = await api("/api/google-sheets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    state.currentDataset = result.dataset;
    state.rows = result.rows;
    await loadDatasets();
    elements["dataset-select"].value = result.dataset.id;
    elements["google-sheet-url"].value = "";
    renderDatasetWorkspace();
    showToast("Google Sheet connected successfully.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setSheetConnecting(false);
  }
}

function setSheetConnecting(isLoading) {
  elements["connect-google-sheet-button"].disabled = isLoading;
  elements["google-sheet-url"].disabled = isLoading;
  elements["connect-google-sheet-button"].textContent = isLoading
    ? "Connecting…"
    : "Connect sheet";
}

async function refreshCurrentSheet() {
  if (!state.currentDataset || state.currentDataset.source_type !== "google_sheet") return;
  elements["refresh-sheet-button"].disabled = true;
  elements["refresh-sheet-button"].textContent = "Refreshing…";
  try {
    const result = await api(`/api/datasets/${state.currentDataset.id}/refresh`, { method: "POST" });
    state.currentDataset = result.dataset;
    state.rows = result.rows;
    await loadDatasets();
    elements["dataset-select"].value = result.dataset.id;
    renderDatasetWorkspace();
    showToast("Google Sheet data refreshed.");
  } catch (error) {
    showToast(error.message, true);
    await selectDataset(state.currentDataset.id);
  } finally {
    elements["refresh-sheet-button"].disabled = false;
    elements["refresh-sheet-button"].textContent = "Refresh now";
  }
}

async function openSampleDashboard() {
  setDemoLoading(true);
  try {
    const result = await api("/api/demo", { method: "POST" });
    showToast(result.reused ? "Opening your sample dashboard." : "Sample dashboard created.");
    window.location.assign(result.redirect_url);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setDemoLoading(false);
  }
}

function setDemoLoading(isLoading) {
  elements["sample-data-button"].disabled = isLoading;
  elements["choose-file-button"].disabled = isLoading;
  elements["sample-data-button"].textContent = isLoading
    ? "Preparing demo…"
    : "Try sample dashboard";
}

function setUploading(isUploading) {
  elements["upload-progress"].classList.toggle("hidden", !isUploading);
  elements["choose-file-button"].disabled = isUploading;
  elements["sample-data-button"].disabled = isUploading;
  elements["choose-file-button"].textContent = isUploading ? "Uploading…" : "Choose file";
}

function renderDatasetOptions() {
  const selectedData = state.currentDataset?.id || elements["dataset-select"].value;
  fillSelect(elements["dataset-select"], state.datasets, "Upload a dataset to begin");
  if (state.datasets.some((item) => item.id === selectedData)) elements["dataset-select"].value = selectedData;
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
  const selected = state.datasets.find((dataset) => dataset.id === datasetId);
  elements["dataset-select"].disabled = true;
  elements["dataset-workspace"].setAttribute("aria-busy", "true");
  elements["page-title"].textContent = selected ? `Loading ${selected.name}…` : "Loading dataset…";
  try {
    const result = await api(`/api/datasets/${datasetId}?limit=100`);
    state.currentDataset = result.dataset;
    state.rows = result.rows;
    renderDatasetWorkspace();
    elements["page-title"].textContent = result.dataset.name;
  } catch (error) {
    elements["page-title"].textContent = "Prepare your data";
    showToast(error.message, true);
  } finally {
    elements["dataset-select"].disabled = false;
    elements["dataset-workspace"].removeAttribute("aria-busy");
  }
}

function clearDatasetWorkspace() {
  state.currentDataset = null;
  state.rows = [];
  elements["dataset-workspace"].classList.add("hidden");
  elements["download-data-button"].disabled = true;
  elements["delete-data-button"].disabled = true;
  elements["refresh-sheet-button"].classList.add("hidden");
  elements["dataset-source-status"].classList.add("hidden");
}

function renderDatasetWorkspace() {
  const dataset = state.currentDataset;
  if (!dataset) return clearDatasetWorkspace();
  elements["dataset-workspace"].classList.remove("hidden");
  elements["download-data-button"].disabled = false;
  elements["delete-data-button"].disabled = false;
  renderSourceStatus(dataset);
  elements["row-count"].textContent = dataset.row_count.toLocaleString();
  elements["column-count"].textContent = dataset.columns.length.toLocaleString();
  elements["preview-count"].textContent = state.rows.length.toLocaleString();
  renderCleaningFields(dataset.columns);
  renderPreview(dataset.columns, state.rows);
}

function renderSourceStatus(dataset) {
  const isSheet = dataset.source_type === "google_sheet";
  elements["refresh-sheet-button"].classList.toggle("hidden", !isSheet);
  elements["dataset-source-status"].classList.toggle("hidden", !isSheet);
  if (!isSheet) return;
  const failed = dataset.last_sync_status === "failed";
  elements["dataset-source-status"].classList.toggle("failed", failed);
  const syncedAt = dataset.last_synced_at
    ? new Date(dataset.last_synced_at).toLocaleString()
    : "Not synced yet";
  const detail = failed
    ? dataset.last_sync_error || "The last refresh failed. Your previous data is still available."
    : `Last refreshed ${syncedAt} · worksheet tab ${dataset.source_sheet_gid}`;
  elements["dataset-source-status"].innerHTML = `
    <div><strong>${failed ? "Google Sheet refresh needs attention" : "Connected Google Sheet"}</strong><span></span></div>
    <small>Manual refresh</small>
  `;
  elements["dataset-source-status"].querySelector("span").textContent = detail;
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
    await loadDatasets();
    showToast("Dataset deleted.");
  } catch (error) {
    showToast(error.message, true);
  }
}

let toastTimer;
function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast show${isError ? " error" : ""}`;
  toastTimer = setTimeout(() => { elements.toast.className = "toast"; }, 3600);
}
