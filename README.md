# DataViz Dash

> Turn spreadsheets into clean, interactive dashboards without writing code.

[![Live demo](https://img.shields.io/badge/Live_demo-Open_DataViz_Dash-111111?style=for-the-badge)](https://dataviz-dash.onrender.com/)
![Release](https://img.shields.io/badge/release-v0.2.1-0f766e?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-Flask-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-Apache_2.0-555555?style=for-the-badge)

DataViz Dash is a no-code spreadsheet analytics workspace created by
**[Naman Sinha](https://github.com/Naman794)**. Upload CSV or Excel files,
prepare the data, build multi-page dashboards, and export presentation-ready
results from one focused browser workspace.

## Try it live

**Public URL:** [https://dataviz-dash.onrender.com/](https://dataviz-dash.onrender.com/)

Create an account or use the available workspace to explore the complete upload,
cleaning, visual-builder, dashboard, and export flow. The service is hosted on
Render, so the first request may take a little longer if the free instance has
been idle.

## Product preview

### 1. Landing page

The public landing page explains the workflow, feature set, and available plans.

![DataViz Dash landing page](docs/images/landing-page-v0.2.png)

### 2. Inside the app

Upload CSV, XLS, or XLSX data, retain the original filename, switch datasets
instantly, inspect rows and columns, apply cleaning rules, and download the
prepared data.

![DataViz Dash data workspace](docs/images/data-workspace-v0.2.png)

### 3. Builder area

Use the expanded Power BI-inspired canvas, contextual inspector, sheet-style
page tabs, zoom controls, and drag-and-resize grid to create reusable dashboards.

![DataViz Dash dashboard builder](docs/images/dashboard-builder-v0.2.png)

## Latest release — v0.2.1

Version **v0.2.1** expands the original MVP into a broader dashboard workspace:

- One-click sample dataset and ready-made dashboard for first-time visitors
- Deployment health and version endpoints for release monitoring
- Privacy-safe public product screenshots
- Redesigned graphite interface with a larger, presentation-oriented canvas
- Dedicated builder with Data, Build, and Format inspector views
- Sheet-style multi-page dashboards
- Drag-and-resize visuals on a persisted 12-column grid
- Fit page, Fit width, Actual size, focus, zoom, grid, undo, and redo controls
- KPI cards, data tables, and eight chart/visual types
- Instant dataset switching without an extra open action
- Automatic preservation of uploaded filenames
- Field profiling, date grouping, sorting, Top-N, duplication, and formatting
- Account-backed datasets, dashboards, usage reporting, and admin controls
- Server-enforced Free and Pro capacity entitlements
- Expanded Free capacity and a 5 GB total-upload allowance for Pro accounts

## Core capabilities

- CSV, XLS, and XLSX upload and preview
- Column renaming and removal
- Missing-value replacement or incomplete-row deletion
- Duplicate and completely empty-row removal
- Cleaned CSV download
- Bar, line, area, pie, scatter, histogram, KPI, and table visuals
- Multi-visual, multi-page dashboard creation and persistence
- Per-visual sorting, Top-N limits, editing, duplication, and responsive sizing
- Month, quarter, and year grouping for date-based visuals
- Chart PNG, dashboard JSON, and print-ready PDF exports
- Anonymous browser-isolated workspaces
- Email/password accounts with persistent workspace ownership
- Protected administrator console with activity and access controls
- Responsive layouts for desktop and smaller screens

## Product flow

1. Try the bundled sample dashboard or upload your own spreadsheet.
2. Apply cleaning rules to prepare the dataset for analysis.
3. Open the builder and choose fields, aggregations, and visual types.
4. Arrange visuals across one or more sheet-style dashboard pages.
5. Save the dashboard for future access or export.

## Free and Pro models

| Capability | Free | Pro |
| --- | ---: | ---: |
| Upcoming price | ₹0 | ₹499/month or ₹4,999/year |
| Maximum upload per file | 50 MB | 100 MB |
| Rows per dataset | 100,000 | 100,000 |
| Total uploaded source data | 150 MB | 5 GB |
| Saved datasets | 3 | 25 |
| Saved dashboards | 2 | 25 |
| Visuals per dashboard | 4 | 12 |
| Pages per dashboard | 1 | 20 |
| Chart data processed | 50,000 rows | 100,000 rows |
| Basic data cleaning | Included | Included |
| Cleaned CSV and chart PNG export | Included | Included |
| Dashboard JSON and print/PDF export | Upgrade required | Included |

The Pro price is a India launch price. Payment checkout is not live
yet, so Pro remains a preview entitlement. At ₹499 per month, DataViz Dash enters
below established business-intelligence tools while its connector,
collaboration, and automation set is still growing. The ₹4,999 annual option
provides roughly two months of savings.

The **5 GB Pro allowance is total account storage measured from original upload
sizes**. It is not a 5 GB single-file limit; individual Pro uploads remain capped
at 100 MB for safe synchronous processing in the current Flask and Pandas
architecture.

## Technology

| Layer | Technology |
| --- | --- |
| Application | Python and Flask |
| Data processing | Pandas, OpenPyXL, and xlrd |
| Database | MongoDB and PyMongo |
| Visualisation | Plotly.js |
| Interface | HTML, CSS, and JavaScript |
| Quality | Pytest, Ruff, and GitHub Actions |
| Packaging | Docker and GitHub Container Registry workflow-ready |
| Hosting | Render |

## Privacy and access

- Uploaded datasets are never given public share links.
- Anonymous data is isolated through a signed browser workspace identifier.
- Registered users can claim an anonymous workspace and access it after signing in.
- Passwords are stored as secure hashes rather than plaintext.
- Plan limits are enforced by the server rather than only hidden in the interface.
- Administrative membership and suspension changes are written to an audit trail.

## Project status

DataViz Dash is under active development. Version **v0.1** established the
data-cleaning and dashboard MVP. Version **v0.2.1** adds the expanded builder,
multi-page dashboards, instant dataset switching, refreshed UI, account usage,
and the revised Free and Pro capacity model.

See the [release history](https://github.com/Naman794/DataViz-Dash/releases) and
the [freemium product plan](docs/FREEMIUM_PLAN.md).

## Creator

**DataViz Dash was designed and built by [Naman Sinha](https://github.com/Naman794).**

## License

Licensed under the [Apache License 2.0](LICENSE).
