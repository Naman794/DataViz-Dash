# DataViz Dash V 0.3.0

Connected spreadsheet sources arrive in DataViz Dash.

## Highlights

- Connect a publicly viewable Google Sheet using its normal sharing URL.
- Detect and retain the selected worksheet tab from the URL `gid`.
- Refresh a connected dataset without uploading the spreadsheet again.
- Keep existing dashboards attached to the same dataset after refresh.
- Display the last successful sync, worksheet identifier, and refresh errors.
- Preserve the last-known-good rows when access, validation, or quota checks fail.
- Enforce one connected Google Sheet on Free and five on Pro.
- Bound every external download by an HTTPS Google hostname, timeout, byte limit,
  row limit, storage quota, and owner check.
- Keep Google sign-in permissions separate from public Sheet imports; no Drive
  scope, access token, or refresh token is stored for this connector.

## Quality

- Automated coverage for URL validation, bounded CSV retrieval, connection
  limits, refresh replacement, and failed-refresh recovery.
- Full compilation, Ruff, JavaScript syntax, and Pytest verification.

## Next milestone

Private Google Sheet authorization and hourly refresh through a dedicated Render
Cron Job remain follow-up work.

---

# DataViz Dash V 0.1

The first working local release of DataViz Dash.

## Highlights

- Upload and preview CSV, XLS, and XLSX datasets.
- Rename or remove columns.
- Fill missing values or delete incomplete rows.
- Remove duplicate and completely empty rows.
- Download cleaned datasets as CSV.
- Build bar, line, area, pie, scatter, and histogram charts.
- Save MongoDB-backed dashboards with up to eight charts.
- Export chart PNGs, dashboard JSON, and print-ready PDFs.
- Run locally with Docker Compose.
- Anonymous browser-isolated workspaces with no public sharing.

## Quality

- Automated CI for compilation, linting, and tests.
- 12 automated tests covering data parsing, cleaning, storage flows, exports, and workspace isolation.

## Security notice

A MongoDB credential appeared in older repository history. Rotate or delete the old Atlas database user before connecting this release to MongoDB Atlas.

## V 0.1.1 stabilization

- Store spreadsheet rows in MongoDB chunks, reducing a 50,000-row dataset from
  50,000 row documents to 50 chunk documents.
- Preserve the active dataset if replacement storage fails during cleaning.
- Keep datasets written by V 0.1 readable without requiring a migration.
- Reject exceptionally large individual rows before they can exceed MongoDB's
  document limit, and apply bounded connection and operation timeouts.
- Validate the 50,000-row path against both the test double and a real MongoDB 7
  service in continuous integration.
