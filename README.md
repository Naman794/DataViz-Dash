# DataViz Dash

DataViz Dash is a local-first Flask application for turning CSV and Excel files into clean, interactive dashboards. The MVP does not require accounts and never creates public share links.

## MVP features

- Upload and preview `.csv`, `.xls`, and `.xlsx` files.
- Rename or remove columns.
- Fill missing values or delete rows with missing values.
- Remove duplicate and completely empty rows.
- Download the cleaned dataset as CSV.
- Build bar, line, area, pie, scatter, and histogram charts.
- Save up to eight charts in a MongoDB-backed dashboard.
- Export chart PNGs, print/save a dashboard as PDF, or download dashboard JSON.

Anonymous ownership is stored in a signed browser cookie. Saved data is only visible to the browser workspace that created it. Clearing that cookie creates a new workspace.

## Quick start with Docker

Docker is the simplest option because it starts both MongoDB and the web application.

```bash
docker compose up --build
```

Open [http://localhost:5000](http://localhost:5000). Stop the application with `Ctrl+C`.

## Run with local Python

Requirements: Python 3.10+ and a running MongoDB instance.

```bash
python -m venv .venv
```

Activate the environment:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install and run:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
python app.py
```

On Windows, copy `.env.example` to `.env` manually. The defaults connect to MongoDB at `mongodb://localhost:27017`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Local development value | Signs the anonymous workspace cookie. Change it outside local development. |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string. |
| `MONGO_DB_NAME` | `dataviz_dash` | Database name. |
| `MAX_UPLOAD_MB` | `10` | Maximum uploaded file size. |
| `MAX_DATASET_ROWS` | `10000` | Maximum rows accepted per dataset. |
| `CHART_ROW_LIMIT` | `10000` | Maximum rows returned to the chart builder. |

## Tests

Tests use an in-memory MongoDB replacement and do not touch a real database.

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check app.py dataviz tests
python -m pytest -q
```

## Project structure

```text
dataviz/
  __init__.py       Flask application factory
  config.py         Environment configuration
  database.py       MongoDB connection and indexes
  routes.py         Web and JSON API routes
  storage.py        Dataset and dashboard persistence
  tabular.py        Spreadsheet parsing and cleaning
static/             Browser JavaScript and styles
templates/          Application shell
tests/              Unit and API tests
app.py              Local and WSGI entry point
```

## Security note

An old MongoDB credential was committed in earlier repository history. Removing it from the current source does not invalidate it. Delete or rotate that Atlas database user before using this repository again, and keep all future credentials in environment variables.
