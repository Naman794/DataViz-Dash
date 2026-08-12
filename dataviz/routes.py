"""Web and JSON routes for the DataViz Dash MVP."""

from __future__ import annotations

import json
import secrets
from datetime import date
from io import BytesIO

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    render_template,
    request,
    send_file,
    session,
)
from pymongo.errors import PyMongoError
from werkzeug.utils import secure_filename

from . import __version__
from .auth import current_user
from .database import get_database
from .demo import (
    SAMPLE_DASHBOARD_TITLE,
    SAMPLE_DATASET_NAME,
    sample_dashboard_payload,
    sample_frame,
)
from .plans import resolve_plan
from .storage import Store
from .tabular import DataLimitError, DataValidationError, clean_frame, parse_upload

bp = Blueprint("main", __name__)
CHART_TYPES = {
    "area",
    "bar",
    "histogram",
    "kpi",
    "line",
    "pie",
    "scatter",
    "table",
}
AGGREGATIONS = {"none", "sum", "average", "count", "minimum", "maximum"}
FILTER_MODES = {"category", "number", "date", "missing"}
MAX_DASHBOARD_FILTERS = 8
MAX_DASHBOARD_PAGES = 20


@bp.before_app_request
def ensure_anonymous_owner():
    session.setdefault("owner_id", secrets.token_urlsafe(24))


def store():
    return Store(get_database())


def owner_id():
    return session["owner_id"]


def active_plan():
    return resolve_plan(current_user())


def record_account_activity(event_type: str, details: dict | None = None):
    user = current_user()
    if user is not None:
        store().record_activity(str(user["_id"]), event_type, details)


def error(message, status=400):
    return jsonify(error=message), status


def plan_limit_error(message, feature):
    return (
        jsonify(
            error=message,
            code="PLAN_LIMIT_REACHED",
            feature=feature,
            upgrade_url="/pricing",
        ),
        403,
    )


def count_label(count, singular, plural=None):
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def uploaded_file_size(upload) -> int:
    stream = upload.stream
    try:
        position = stream.tell()
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(position)
        return max(0, int(size))
    except (AttributeError, OSError, TypeError, ValueError):
        return max(0, int(upload.content_length or 0))


def storage_limit_label(megabytes: int) -> str:
    if megabytes >= 1024 and megabytes % 1024 == 0:
        return f"{megabytes // 1024} GB"
    return f"{megabytes} MB"


@bp.get("/")
def landing():
    return render_template("landing.html", plan=active_plan())


@bp.get("/app")
def index():
    plan = active_plan()
    return render_template(
        "workspace.html",
        plan=plan,
        max_upload_mb=plan["max_upload_mb"],
        max_dataset_rows=plan["max_dataset_rows"],
        chart_row_limit=plan["chart_row_limit"],
    )


@bp.get("/builder")
def builder():
    return render_builder()


@bp.get("/builder/<dashboard_id>")
def edit_dashboard(dashboard_id):
    if store().get_dashboard(owner_id(), dashboard_id) is None:
        abort(404)
    return render_builder(dashboard_id)


def render_builder(dashboard_id: str = ""):
    plan = active_plan()
    return render_template(
        "builder.html",
        plan=plan,
        initial_dashboard_id=dashboard_id,
        chart_row_limit=plan["chart_row_limit"],
    )


@bp.get("/pricing")
def pricing():
    return render_template(
        "pricing.html",
        plan=active_plan(),
        free_plan=resolve_plan(),
        pro_plan=resolve_plan({"plan": "pro"}),
    )


@bp.get("/api/health")
def health():
    try:
        get_database().command("ping")
        return jsonify(status="ok", database="connected", version=__version__)
    except PyMongoError:
        return (
            jsonify(
                status="degraded",
                database="unavailable",
                version=__version__,
            ),
            503,
        )


@bp.get("/api/version")
def version():
    return jsonify(name="DataViz Dash", version=__version__)


@bp.post("/api/demo")
def create_demo():
    plan = active_plan()
    repository = store()
    datasets = repository.list_datasets(owner_id())
    dataset = next(
        (item for item in datasets if item["name"] == SAMPLE_DATASET_NAME),
        None,
    )
    dashboard = None
    if dataset is not None:
        dashboard = next(
            (
                item
                for item in repository.list_dashboards(owner_id())
                if item["title"] == SAMPLE_DASHBOARD_TITLE
                and item["dataset_id"] == dataset["id"]
            ),
            None,
        )

    if dataset is not None and dashboard is not None:
        return jsonify(
            dataset=dataset,
            dashboard=dashboard,
            redirect_url=f"/builder/{dashboard['id']}",
            reused=True,
        )

    if repository.count_dashboards(owner_id()) >= plan["max_dashboards"]:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{count_label(plan['max_dashboards'], 'saved dashboard')}.",
            "saved_dashboards",
        )
    if dataset is None and repository.count_datasets(owner_id()) >= plan["max_datasets"]:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{count_label(plan['max_datasets'], 'saved dataset')}.",
            "saved_datasets",
        )

    created_dataset = dataset is None
    if created_dataset:
        dataset = repository.create_dataset(
            owner_id(),
            SAMPLE_DATASET_NAME,
            sample_frame(),
        )

    payload, validation_error = validate_dashboard_payload(
        sample_dashboard_payload(dataset["id"], plan["max_charts"])
    )
    if validation_error:
        return error(validation_error)
    dashboard = repository.create_dashboard(owner_id(), payload)
    record_account_activity(
        "demo.created",
        {"dataset_id": dataset["id"], "dashboard_id": dashboard["id"]},
    )
    return (
        jsonify(
            dataset=dataset,
            dashboard=dashboard,
            redirect_url=f"/builder/{dashboard['id']}",
            reused=False,
        ),
        201,
    )


@bp.get("/api/datasets")
def list_datasets():
    return jsonify(datasets=store().list_datasets(owner_id()))


@bp.post("/api/datasets")
def upload_dataset():
    plan = active_plan()
    maximum_request_bytes = (plan["max_upload_mb"] + 1) * 1024 * 1024
    if request.content_length and request.content_length > maximum_request_bytes:
        message = f"File is too large. Maximum size is {plan['max_upload_mb']} MB."
        if plan["name"] == "free":
            return plan_limit_error(message, "upload_size")
        return error(message, 413)
    upload = request.files.get("file")
    if upload is None:
        return error("Choose a CSV, XLS, or XLSX file.")
    repository = store()
    source_size_bytes = uploaded_file_size(upload)
    max_storage_bytes = plan["max_storage_mb"] * 1024 * 1024
    if repository.total_source_bytes(owner_id()) + source_size_bytes > max_storage_bytes:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{storage_limit_label(plan['max_storage_mb'])} of uploaded data.",
            "storage_capacity",
        )
    if repository.count_datasets(owner_id()) >= plan["max_datasets"]:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{count_label(plan['max_datasets'], 'saved dataset')}.",
            "saved_datasets",
        )
    try:
        frame = parse_upload(
            upload,
            plan["max_dataset_rows"],
            max_bytes=plan["max_upload_mb"] * 1024 * 1024,
        )
    except DataLimitError as exc:
        if plan["name"] == "free":
            return plan_limit_error(str(exc), exc.feature)
        return error(str(exc))
    except DataValidationError as exc:
        return error(str(exc))

    filename = secure_filename(upload.filename or "dataset") or "dataset"
    try:
        dataset = repository.create_dataset(
            owner_id(), filename, frame, source_size_bytes=source_size_bytes
        )
    except DataValidationError as exc:
        return error(str(exc))
    stored_dataset = repository.get_dataset(owner_id(), dataset["id"])
    record_account_activity(
        "dataset.uploaded",
        {
            "dataset_id": dataset["id"],
            "filename": dataset["name"],
            "row_count": dataset["row_count"],
        },
    )
    return jsonify(
        dataset=dataset,
        rows=repository.get_rows(stored_dataset, limit=100),
    ), 201


@bp.get("/api/datasets/<dataset_id>")
def get_dataset(dataset_id):
    repository = store()
    dataset = repository.get_dataset(owner_id(), dataset_id)
    if dataset is None:
        return error("Dataset not found.", 404)

    requested_limit = request.args.get("limit", 100, type=int)
    limit = max(1, min(requested_limit, active_plan()["chart_row_limit"]))
    return jsonify(
        dataset=repository.serialize_dataset(dataset),
        rows=repository.get_rows(dataset, limit),
        truncated=dataset["row_count"] > limit,
    )


@bp.post("/api/datasets/<dataset_id>/clean")
def clean_dataset(dataset_id):
    repository = store()
    dataset = repository.get_dataset(owner_id(), dataset_id)
    if dataset is None:
        return error("Dataset not found.", 404)

    operations = request.get_json(silent=True) or {}
    try:
        frame, summary = clean_frame(repository.get_frame(dataset), operations)
        updated = repository.replace_dataset(dataset, frame)
    except DataValidationError as exc:
        return error(str(exc))

    record_account_activity(
        "dataset.cleaned",
        {"dataset_id": dataset_id, "row_count": updated["row_count"]},
    )

    return jsonify(
        dataset=updated,
        rows=repository.get_rows(dataset, 100),
        summary=summary,
    )


@bp.get("/api/datasets/<dataset_id>/download")
def download_dataset(dataset_id):
    repository = store()
    dataset = repository.get_dataset(owner_id(), dataset_id)
    if dataset is None:
        return error("Dataset not found.", 404)
    frame = repository.get_frame(dataset)
    record_account_activity(
        "dataset.exported",
        {"dataset_id": dataset_id, "filename": dataset["name"]},
    )
    output = BytesIO(frame.to_csv(index=False).encode("utf-8"))
    base_name = dataset["name"].rsplit(".", 1)[0]
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{base_name}-cleaned.csv",
    )


@bp.delete("/api/datasets/<dataset_id>")
def delete_dataset(dataset_id):
    if not store().delete_dataset(owner_id(), dataset_id):
        return error("Dataset not found.", 404)
    record_account_activity("dataset.deleted", {"dataset_id": dataset_id})
    return Response(status=204)


@bp.get("/api/dashboards")
def list_dashboards():
    return jsonify(dashboards=store().list_dashboards(owner_id()))


@bp.post("/api/dashboards")
def create_dashboard():
    plan = active_plan()
    if store().count_dashboards(owner_id()) >= plan["max_dashboards"]:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{count_label(plan['max_dashboards'], 'saved dashboard')}.",
            "saved_dashboards",
        )
    raw_payload = request.get_json(silent=True) or {}
    pages = raw_payload.get("pages")
    if isinstance(pages, list) and len(pages) > plan["max_pages"]:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{count_label(plan['max_pages'], 'dashboard page')} per dashboard.",
            "dashboard_pages",
        )
    charts = raw_payload.get("charts")
    if isinstance(charts, list) and len(charts) > plan["max_charts"]:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{count_label(plan['max_charts'], 'chart')} per dashboard.",
            "charts_per_dashboard",
        )
    payload, validation_error = validate_dashboard_payload(raw_payload)
    if validation_error:
        return error(validation_error)
    dashboard = store().create_dashboard(owner_id(), payload)
    record_account_activity(
        "dashboard.created",
        {"dashboard_id": dashboard["id"], "title": dashboard["title"]},
    )
    return jsonify(dashboard=dashboard), 201


@bp.get("/api/dashboards/<dashboard_id>")
def get_dashboard(dashboard_id):
    dashboard = store().get_dashboard(owner_id(), dashboard_id)
    if dashboard is None:
        return error("Dashboard not found.", 404)
    return jsonify(dashboard=dashboard)


@bp.put("/api/dashboards/<dashboard_id>")
def update_dashboard(dashboard_id):
    plan = active_plan()
    raw_payload = request.get_json(silent=True) or {}
    pages = raw_payload.get("pages")
    if isinstance(pages, list) and len(pages) > plan["max_pages"]:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{count_label(plan['max_pages'], 'dashboard page')} per dashboard.",
            "dashboard_pages",
        )
    charts = raw_payload.get("charts")
    if isinstance(charts, list) and len(charts) > plan["max_charts"]:
        return plan_limit_error(
            f"Your {plan['label']} plan supports "
            f"{count_label(plan['max_charts'], 'chart')} per dashboard.",
            "charts_per_dashboard",
        )
    payload, validation_error = validate_dashboard_payload(raw_payload)
    if validation_error:
        return error(validation_error)
    dashboard = store().update_dashboard(owner_id(), dashboard_id, payload)
    if dashboard is None:
        return error("Dashboard not found.", 404)
    record_account_activity(
        "dashboard.updated",
        {"dashboard_id": dashboard["id"], "title": dashboard["title"]},
    )
    return jsonify(dashboard=dashboard)


@bp.delete("/api/dashboards/<dashboard_id>")
def delete_dashboard(dashboard_id):
    if not store().delete_dashboard(owner_id(), dashboard_id):
        return error("Dashboard not found.", 404)
    record_account_activity("dashboard.deleted", {"dashboard_id": dashboard_id})
    return Response(status=204)


@bp.get("/api/dashboards/<dashboard_id>/export")
def export_dashboard(dashboard_id):
    if not active_plan()["dashboard_exports"]:
        return plan_limit_error(
            "Dashboard JSON export is available on the Pro plan.",
            "dashboard_json_export",
        )
    dashboard = store().get_dashboard(owner_id(), dashboard_id)
    if dashboard is None:
        return error("Dashboard not found.", 404)
    record_account_activity(
        "dashboard.exported",
        {"dashboard_id": dashboard["id"], "title": dashboard["title"]},
    )
    output = BytesIO(json.dumps(dashboard, indent=2).encode("utf-8"))
    filename = secure_filename(dashboard["title"]) or "dashboard"
    return send_file(
        output,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"{filename}.json",
    )


def validate_dashboard_payload(raw_payload):
    payload = raw_payload or {}
    title = str(payload.get("title", "")).strip()
    dataset_id = str(payload.get("dataset_id", "")).strip()
    raw_charts = payload.get("charts")
    raw_pages = payload.get("pages")
    filters = payload.get("filters", [])
    page_specs = []

    if raw_pages is None:
        charts = raw_charts
        page_specs = [
            {
                "id": "page-1",
                "title": "Page 1",
                "count": len(charts) if isinstance(charts, list) else 0,
            }
        ]
    else:
        max_pages = min(active_plan()["max_pages"], MAX_DASHBOARD_PAGES)
        if not isinstance(raw_pages, list) or not 1 <= len(raw_pages) <= max_pages:
            return None, f"A dashboard must contain between 1 and {max_pages} pages."
        charts = []
        seen_page_ids = set()
        for index, page in enumerate(raw_pages):
            if not isinstance(page, dict):
                return None, "Every dashboard page must be a valid object."
            page_charts = page.get("charts", [])
            if not isinstance(page_charts, list):
                return None, "Every dashboard page must contain a chart list."
            page_id = str(page.get("id") or f"page-{index + 1}")[:100]
            if page_id in seen_page_ids:
                return None, "Dashboard page IDs must be unique."
            seen_page_ids.add(page_id)
            page_title = str(page.get("title") or f"Page {index + 1}").strip()[:50]
            page_specs.append({"id": page_id, "title": page_title, "count": len(page_charts)})
            charts.extend(page_charts)

    if not title or len(title) > 100:
        return None, "Dashboard title must contain 1 to 100 characters."
    dataset = store().get_dataset(owner_id(), dataset_id)
    if dataset is None:
        return None, "Select a valid dataset."
    max_charts = active_plan()["max_charts"]
    if not isinstance(charts, list) or not 1 <= len(charts) <= max_charts:
        return None, (
            f"Your current plan supports between 1 and {max_charts} charts "
            "per dashboard."
        )
    validated_filters, filter_error = validate_dashboard_filters(filters, dataset)
    if filter_error:
        return None, filter_error

    validated_charts = []
    columns = set(dataset["columns"])
    for chart in charts:
        if not isinstance(chart, dict):
            return None, "Every chart must be a valid object."
        chart_type = chart.get("type")
        x_column = chart.get("x")
        y_column = chart.get("y") or None
        if not isinstance(chart_type, str) or chart_type not in CHART_TYPES:
            return None, "A chart contains an unsupported type."
        if not isinstance(x_column, str) or x_column not in columns:
            return None, "A chart references an unknown X-axis column."
        if y_column and (not isinstance(y_column, str) or y_column not in columns):
            return None, "A chart references an unknown Y-axis column."
        aggregation = chart.get("aggregation")
        if not isinstance(aggregation, str):
            aggregation = "none"
        if aggregation in {"sum", "average", "minimum", "maximum"}:
            if not y_column:
                return None, "This aggregation requires a Y-axis column."
            if dataset.get("column_types", {}).get(y_column) != "number":
                return None, "This aggregation requires a numeric Y-axis column."
        date_group = chart.get("date_group", "none")
        if not isinstance(date_group, str) or date_group not in {
            "none",
            "month",
            "quarter",
            "year",
        }:
            date_group = "none"
        if date_group != "none" and chart_type not in {"area", "bar", "line", "pie"}:
            return None, "Date grouping is not supported for this visual type."
        raw_layout = chart.get("layout") if isinstance(chart.get("layout"), dict) else {}
        default_width = 12 if chart.get("size") == "full" else 6
        width = raw_layout.get("w", default_width)
        height = raw_layout.get("h", 7)
        x_position = raw_layout.get("x", 0)
        y_position = raw_layout.get("y", 0)
        width = width if isinstance(width, int) and not isinstance(width, bool) else default_width
        height = height if isinstance(height, int) and not isinstance(height, bool) else 7
        x_position = (
            x_position
            if isinstance(x_position, int) and not isinstance(x_position, bool)
            else 0
        )
        y_position = (
            y_position
            if isinstance(y_position, int) and not isinstance(y_position, bool)
            else 0
        )
        width = min(12, max(3, width))
        height = min(16, max(4, height))
        x_position = min(12 - width, max(0, x_position))
        y_position = max(0, y_position)
        validated_charts.append(
            {
                "id": str(chart.get("id") or secrets.token_hex(6)),
                "title": str(chart.get("title") or f"{chart_type.title()} chart")[:100],
                "type": chart_type,
                "x": x_column,
                "y": y_column,
                "aggregation": aggregation if aggregation in AGGREGATIONS else "none",
                "sort": chart.get("sort")
                if isinstance(chart.get("sort"), str)
                and chart.get("sort") in {"default", "ascending", "descending"}
                else "default",
                "top_n": chart.get("top_n")
                if isinstance(chart.get("top_n"), int)
                and not isinstance(chart.get("top_n"), bool)
                and chart.get("top_n") in {0, 5, 10, 20}
                else 0,
                "size": chart.get("size")
                if isinstance(chart.get("size"), str)
                and chart.get("size") in {"half", "full"}
                else "half",
                "date_group": date_group,
                "layout": {
                    "x": x_position,
                    "y": y_position,
                    "w": width,
                    "h": height,
                },
            }
        )

    validated_pages = []
    offset = 0
    for page in page_specs:
        page_charts = validated_charts[offset : offset + page["count"]]
        offset += page["count"]
        validated_pages.append(
            {"id": page["id"], "title": page["title"], "charts": page_charts}
        )
    requested_active_page = str(payload.get("active_page_id") or "")
    active_page_id = (
        requested_active_page
        if any(page["id"] == requested_active_page for page in validated_pages)
        else validated_pages[0]["id"]
    )

    return {
        "title": title,
        "dataset_id": dataset_id,
        "charts": validated_charts,
        "pages": validated_pages,
        "active_page_id": active_page_id,
        "filters": validated_filters,
    }, None


def validate_dashboard_filters(filters, dataset):
    if not isinstance(filters, list) or len(filters) > MAX_DASHBOARD_FILTERS:
        return None, (
            f"A dashboard can contain up to {MAX_DASHBOARD_FILTERS} global filters."
        )

    columns = set(dataset["columns"])
    validated = []
    for item in filters:
        if not isinstance(item, dict):
            return None, "Every dashboard filter must be a valid object."
        column = item.get("column")
        mode = item.get("mode")
        if not isinstance(column, str) or column not in columns:
            return None, "A dashboard filter references an unknown column."
        if not isinstance(mode, str) or mode not in FILTER_MODES:
            return None, "A dashboard filter has an unsupported mode."

        document = {
            "id": str(item.get("id") or secrets.token_hex(6))[:100],
            "column": column,
            "mode": mode,
        }
        if mode == "category":
            value = str(item.get("value", ""))
            if not value:
                return None, "Category filters require a value."
            if len(value) > 500:
                return None, "Category filter values cannot exceed 500 characters."
            document["value"] = value
        elif mode == "number":
            raw_minimum = item.get("minimum")
            raw_maximum = item.get("maximum")
            minimum = optional_number(raw_minimum)
            maximum = optional_number(raw_maximum)
            if (raw_minimum is not None and raw_minimum != "" and minimum is None) or (
                raw_maximum is not None and raw_maximum != "" and maximum is None
            ):
                return None, "Number filter boundaries must be valid numbers."
            if minimum is None and maximum is None:
                return None, "Number filters require a minimum or maximum."
            if minimum is not None and maximum is not None and minimum > maximum:
                return None, "A number filter minimum cannot exceed its maximum."
            document.update({"minimum": minimum, "maximum": maximum})
        elif mode == "date":
            raw_start = item.get("start")
            raw_end = item.get("end")
            start = optional_iso_date(raw_start)
            end = optional_iso_date(raw_end)
            if (raw_start is not None and raw_start != "" and start is None) or (
                raw_end is not None and raw_end != "" and end is None
            ):
                return None, "Date filter boundaries must use YYYY-MM-DD."
            if start is None and end is None:
                return None, "Date filters require a start or end date."
            if start and end and start > end:
                return None, "A date filter start cannot be after its end."
            document.update({"start": start, "end": end})
        else:
            behavior = item.get("behavior")
            if not isinstance(behavior, str) or behavior not in {"only", "exclude"}:
                return None, "Missing-value filters must include or exclude blanks."
            document["behavior"] = behavior
        validated.append(document)
    return validated, None


def optional_number(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def optional_iso_date(value):
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None
