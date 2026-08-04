from io import BytesIO


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


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Upload, preview and clean" in response.data


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
    assert exported.status_code == 200
    assert exported.mimetype == "application/json"
    assert b"Updated sales overview" in exported.data

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
