from io import BytesIO

import mongomock

import dataviz.storage as storage_module
from dataviz import create_app


def upload_dataset(client):
    response = client.post(
        "/api/datasets",
        data={
            "file": (
                BytesIO(b"Region,Sales,Notes\nNorth,10,\nNorth,10,\nSouth,,late\n,,\n"),
                "sales.csv",
            )
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    return response.get_json()["dataset"]


def test_landing_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Turn spreadsheets into clear, interactive dashboards" in response.data
    assert b'href="/app"' in response.data
    assert b">50,000<" in response.data
    assert b"rows on Pro" in response.data
    assert b"No account required" in response.data

    assert client.get("/static/images/data-workspace.png").status_code == 200
    assert client.get("/static/images/chart-builder.png").status_code == 200


def test_workspace_page_loads(client):
    response = client.get("/app")
    assert response.status_code == 200
    assert b"Upload, preview and clean" in response.data
    assert b"maximum 10 MB and 100 rows" in response.data
    assert b'href="/"' in response.data
    assert b'href="/builder"' in response.data


def test_dedicated_builder_page_and_saved_dashboard_route(client):
    builder = client.get("/builder")
    assert builder.status_code == 200
    assert b"Dashboard canvas" in builder.data
    assert b"KPI" in builder.data
    assert b"Table" in builder.data
    assert b'data-chart-row-limit="100"' in builder.data

    dataset = upload_dataset(client)
    payload = {
        "title": "Analysis workspace",
        "dataset_id": dataset["id"],
        "charts": [
            {
                "title": "Total sales",
                "type": "kpi",
                "x": "Region",
                "y": "Sales",
                "aggregation": "maximum",
                "sort": "descending",
                "top_n": 5,
                "size": "half",
            },
            {
                "title": "Sales records",
                "type": "table",
                "x": "Region",
                "y": "Sales",
                "aggregation": "none",
                "size": "full",
            },
        ],
    }
    created = client.post("/api/dashboards", json=payload)
    assert created.status_code == 201
    dashboard = created.get_json()["dashboard"]
    assert dashboard["charts"][0]["type"] == "kpi"
    assert dashboard["charts"][0]["aggregation"] == "maximum"
    assert dashboard["charts"][0]["top_n"] == 5
    assert dashboard["charts"][1]["size"] == "full"

    edit_page = client.get(f"/builder/{dashboard['id']}")
    assert edit_page.status_code == 200
    assert f'data-initial-dashboard-id="{dashboard["id"]}"'.encode() in edit_page.data
    assert client.get("/builder/not-a-dashboard").status_code == 404
    assert client.application.test_client().get(
        f"/builder/{dashboard['id']}"
    ).status_code == 404


def test_oversized_upload_returns_configured_limit():
    mongo_client = mongomock.MongoClient()
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "MONGO_CLIENT": mongo_client,
            "MONGO_DB_NAME": "dataviz_test",
            "MAX_UPLOAD_MB": 1,
            "MAX_CONTENT_LENGTH": 1024 * 1024,
        }
    )
    user_id = mongo_client.dataviz_test.users.insert_one(
        {"email": "pro@example.com", "password_hash": "unused", "plan": "pro"}
    ).inserted_id
    client = application.test_client()
    with client.session_transaction() as session:
        session["user_id"] = str(user_id)
        session["owner_id"] = str(user_id)

    response = client.post(
        "/api/datasets",
        data={"file": (BytesIO(b"x" * (2 * 1024 * 1024)), "large.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.get_json()["error"] == "File is too large. Maximum size is 1 MB."
    mongo_client.close()


def test_dataset_clean_download_and_delete_flow(client):
    dataset = upload_dataset(client)
    assert dataset["row_count"] == 4

    response = client.post(
        f"/api/datasets/{dataset['id']}/clean",
        json={
            "rename": {"Sales": "Revenue"},
            "remove_columns": ["Notes"],
            "remove_duplicates": True,
            "remove_empty_rows": True,
            "missing": {"strategy": "fill", "columns": ["Revenue"], "value": 0},
        },
    )
    assert response.status_code == 200
    result = response.get_json()
    assert result["dataset"]["columns"] == ["Region", "Revenue"]
    assert result["dataset"]["row_count"] == 2

    download = client.get(f"/api/datasets/{dataset['id']}/download")
    assert download.status_code == 200
    assert download.mimetype == "text/csv"
    assert b"Region,Revenue" in download.data

    deleted = client.delete(f"/api/datasets/{dataset['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/datasets/{dataset['id']}").status_code == 404


def test_dashboard_save_update_export_and_delete(client):
    dataset = upload_dataset(client)
    payload = {
        "title": "Sales overview",
        "dataset_id": dataset["id"],
        "charts": [
            {
                "id": "chart-1",
                "title": "Sales by region",
                "type": "bar",
                "x": "Region",
                "y": "Sales",
                "aggregation": "sum",
            }
        ],
    }
    created = client.post("/api/dashboards", json=payload)
    assert created.status_code == 201
    dashboard = created.get_json()["dashboard"]

    payload["title"] = "Updated sales overview"
    updated = client.put(f"/api/dashboards/{dashboard['id']}", json=payload)
    assert updated.status_code == 200
    assert updated.get_json()["dashboard"]["title"] == payload["title"]

    exported = client.get(f"/api/dashboards/{dashboard['id']}/export")
    assert exported.status_code == 403
    assert exported.get_json()["code"] == "PLAN_LIMIT_REACHED"

    deleted = client.delete(f"/api/dashboards/{dashboard['id']}")
    assert deleted.status_code == 204


def test_anonymous_workspaces_are_isolated(app):
    first_client = app.test_client()
    second_client = app.test_client()
    dataset = upload_dataset(first_client)

    assert first_client.get(f"/api/datasets/{dataset['id']}").status_code == 200
    assert second_client.get(f"/api/datasets/{dataset['id']}").status_code == 404


def test_invalid_upload_is_rejected(client):
    response = client.post(
        "/api/datasets",
        data={"file": (BytesIO(b"not a spreadsheet"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "CSV" in response.get_json()["error"]


def test_unstorable_wide_row_returns_a_clear_error(client, monkeypatch):
    monkeypatch.setattr(storage_module, "ROW_CHUNK_TARGET_BYTES", 100)

    response = client.post(
        "/api/datasets",
        data={"file": (BytesIO(b"Value\n" + b"x" * 200), "wide.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "row is too large" in response.get_json()["error"]


def test_free_dataset_limit_returns_upgrade_response(client):
    upload_dataset(client)
    response = client.post(
        "/api/datasets",
        data={"file": (BytesIO(b"Value\n1\n"), "second.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "Your Free plan supports 1 saved dataset.",
        "code": "PLAN_LIMIT_REACHED",
        "feature": "saved_datasets",
        "upgrade_url": "/pricing",
    }


def test_free_row_limit_returns_upgrade_response(client):
    rows = b"Value\n" + b"1\n" * 101
    response = client.post(
        "/api/datasets",
        data={"file": (BytesIO(rows), "too-many-rows.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 403
    assert response.get_json()["feature"] == "dataset_rows"


def test_free_chart_limit_returns_upgrade_response(client):
    dataset = upload_dataset(client)
    chart = {
        "title": "Sales",
        "type": "bar",
        "x": "Region",
        "y": "Sales",
        "aggregation": "sum",
    }
    response = client.post(
        "/api/dashboards",
        json={
            "title": "Too many charts",
            "dataset_id": dataset["id"],
            "charts": [chart, chart, chart],
        },
    )

    assert response.status_code == 403
    assert response.get_json()["feature"] == "charts_per_dashboard"
