"""Web and JSON routes for the DataViz Dash MVP."""

from __future__ import annotations

import json
import secrets
from io import BytesIO

from flask import (
    Blueprint,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
    session,
)
from pymongo.errors import PyMongoError
from werkzeug.utils import secure_filename

from .auth import current_user
from .database import get_database
from .plans import resolve_plan
from .storage import Store
from .tabular import DataLimitError, DataValidationError, clean_frame, parse_upload

bp = Blueprint("main", __name__)
CHART_TYPES = {"bar", "line", "area", "pie", "scatter", "histogram"}


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
        return jsonify(status="ok", database="connected")
    except PyMongoError:
        return jsonify(status="degraded", database="unavailable"), 503


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
        dataset = repository.create_dataset(owner_id(), filename, frame)
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
    charts = payload.get("charts")

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

    validated_charts = []
    columns = set(dataset["columns"])
    for chart in charts:
        if not isinstance(chart, dict):
            return None, "Every chart must be a valid object."
        chart_type = chart.get("type")
        x_column = chart.get("x")
        y_column = chart.get("y") or None
        if chart_type not in CHART_TYPES:
            return None, "A chart contains an unsupported type."
        if x_column not in columns:
            return None, "A chart references an unknown X-axis column."
        if y_column and y_column not in columns:
            return None, "A chart references an unknown Y-axis column."
        aggregation = chart.get("aggregation")
        if aggregation in {"sum", "average"}:
            if not y_column:
                return None, "Sum and average charts require a Y-axis column."
            if dataset.get("column_types", {}).get(y_column) != "number":
                return None, "Sum and average require a numeric Y-axis column."
        validated_charts.append(
            {
                "id": str(chart.get("id") or secrets.token_hex(6)),
                "title": str(chart.get("title") or f"{chart_type.title()} chart")[:100],
                "type": chart_type,
                "x": x_column,
                "y": y_column,
                "aggregation": aggregation
                if aggregation in {"none", "sum", "average", "count"}
                else "none",
            }
        )

    return {
        "title": title,
        "dataset_id": dataset_id,
        "charts": validated_charts,
    }, None
