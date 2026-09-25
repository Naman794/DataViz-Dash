# Dashboard workspace

The builder uses a compact title and save bar, a dataset/chart/filter toolbar,
a large canvas, and a searchable data sidebar. Select Add chart to configure a
visual. Select a card title or its Edit menu item to change it. Clicking the
empty canvas returns to the data fields. Existing dashboards remain compatible.

## Drag fields onto the dashboard

Drag a field from the right-side Data list to the canvas. Text fields create a
count-by-category bar chart, dates create a count-by-date line chart, and numbers
create a distribution histogram. Drop onto an existing card to replace its
category (text/date) or value (number). Histogram drops replace the histogram
field. Existing chart titles and layouts are preserved. Changes support Undo,
Redo and Save. The canvas and destination card highlight during dragging.
Desktop browsers support this interaction; the Add chart controls remain available
for touch and keyboard use.

## Controls

- **Add filter:** exact category, numeric range, ISO date range, or missing values.
  Up to eight filters combine with AND and apply to every chart on every page.
  Remove an individual chip or select Clear filters to restore the loaded rows.
- **Date range:** available for declared date columns or text columns whose
  first 100 nonblank sample values contain valid ISO dates. Both boundaries are
  inclusive. Charts and filters operate on the loaded, plan-limited data; the
  row summary identifies truncated datasets.
- **Tables:** search, sort column headers, and browse in pages of 20. Format
  controls can turn numeric value bars off. Bars show relative absolute values;
  signed numbers remain visible. Search/sort/pagination are temporary viewing
  controls; the value-bar preference is saved with the visual.
- **Layout:** drag a card's handle; resize from the bottom-right corner. Layouts
  snap to the existing grid and reject overlaps. Undo and Redo restore layouts.
  On phones, cards stack for readability; moving/resizing remains a desktop action.
- **Save:** saves the current dashboard. Edits made during the request remain
  unsaved and visible. Failed saves retain the workspace for retry.
- **Reset:** restores the last successfully saved snapshot after confirmation;
  for a new dashboard, clears its unsaved content. Leaving with unsaved dashboard
  changes triggers the browser's warning.

CSV/XLS/XLSX ingestion remains in the Data workspace. This update does not add
an Excel worksheet picker (the current importer reads the first worksheet).
The older retention/Sheet URL changes remain in separate PR #21.

## Validation

Run `python -m pytest -q`, `python -m ruff check app.py dataviz tests`,
`node --check static/js/builder.js`, and `node --test tests/builder-model.test.cjs`.
The JavaScript tests use Node's built-in runner with no npm dependencies.

The optional DOM interaction regression test is `node tests/builder-field-drop.cjs`
with `jsdom` installed. It checks drops, Undo, stale/unknown fields and chart limits.
