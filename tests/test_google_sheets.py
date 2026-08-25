from __future__ import annotations

import pandas as pd
import pytest

import dataviz.routes as routes_module
from dataviz.google_sheets import (
    GoogleSheetError,
    GoogleSheetReference,
    GoogleSheetSnapshot,
    fetch_google_sheet,
    parse_google_sheet_url,
)


class FakeResponse:
    def __init__(self, payload=b"Region,Sales\nNorth,10\n", status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/csv"}
        self.closed = False

    def iter_content(self, chunk_size):
        for start in range(0, len(self.payload), chunk_size):
            yield self.payload[start : start + chunk_size]

    def close(self):
        self.closed = True


def snapshot(values=(10, 20)):
    reference = GoogleSheetReference(
        "1abcdefghijklmnopqrstuvwxyzABCDE", "456"
    )
    return GoogleSheetSnapshot(
        pd.DataFrame({"Region": ["North", "South"], "Sales": list(values)}),
        reference,
        42,
        "Google Sheet 1abcdefg (tab 456).csv",
    )


def test_google_sheet_url_accepts_only_google_spreadsheets():
    reference = parse_google_sheet_url(
        "https://docs.google.com/spreadsheets/d/"
        "1abcdefghijklmnopqrstuvwxyzABCDE/edit#gid=456"
    )
    assert reference.spreadsheet_id == "1abcdefghijklmnopqrstuvwxyzABCDE"
    assert reference.sheet_gid == "456"
    assert reference.csv_url.startswith(
        "https://docs.google.com/spreadsheets/d/1abcdefghijklmnopqrstuvwxyzABCDE/gviz/tq?"
    )

    invalid_links = [
        "http://docs.google.com/spreadsheets/d/1abcdefghijklmnopqrstuvwxyzABCDE/edit",
        "https://example.com/spreadsheets/d/1abcdefghijklmnopqrstuvwxyzABCDE/edit",
        "https://docs.google.com/document/d/1abcdefghijklmnopqrstuvwxyzABCDE/edit",
        "https://docs.google.com/spreadsheets/d/too-short/edit",
    ]
    for link in invalid_links:
        with pytest.raises(GoogleSheetError):
            parse_google_sheet_url(link)


def test_google_sheet_fetch_is_bounded_and_parses_csv():
    calls = []
    response = FakeResponse()

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    result = fetch_google_sheet(
        "https://docs.google.com/spreadsheets/d/"
        "1abcdefghijklmnopqrstuvwxyzABCDE/edit#gid=456",
        max_rows=100,
        max_bytes=1024,
        http_get=fake_get,
    )

    assert result.frame.to_dict(orient="records") == [
        {"Region": "North", "Sales": 10}
    ]
    assert calls[0][0] == result.reference.csv_url
    assert calls[0][1]["allow_redirects"] is False
    assert response.closed is True


def test_connect_refresh_and_preserve_last_good_sheet_data(client, monkeypatch):
    monkeypatch.setattr(routes_module, "fetch_google_sheet", lambda *args, **kwargs: snapshot())
    connected = client.post(
        "/api/google-sheets",
        json={
            "url": "https://docs.google.com/spreadsheets/d/"
            "1abcdefghijklmnopqrstuvwxyzABCDE/edit#gid=456"
        },
    )
    assert connected.status_code == 201
    dataset = connected.get_json()["dataset"]
    assert dataset["source_type"] == "google_sheet"
    assert dataset["source_sheet_gid"] == "456"
    assert dataset["last_sync_status"] == "success"
    assert dataset["row_count"] == 2

    monkeypatch.setattr(
        routes_module,
        "fetch_google_sheet",
        lambda *args, **kwargs: snapshot((30, 40)),
    )
    refreshed = client.post(f"/api/datasets/{dataset['id']}/refresh")
    assert refreshed.status_code == 200
    assert [row["Sales"] for row in refreshed.get_json()["rows"]] == [30, 40]

    def fail_fetch(*args, **kwargs):
        raise GoogleSheetError("Sheet access was removed.")

    monkeypatch.setattr(routes_module, "fetch_google_sheet", fail_fetch)
    failed = client.post(f"/api/datasets/{dataset['id']}/refresh")
    assert failed.status_code == 400
    after_failure = client.get(f"/api/datasets/{dataset['id']}").get_json()
    assert after_failure["dataset"]["last_sync_status"] == "failed"
    assert after_failure["dataset"]["last_sync_error"] == "Sheet access was removed."
    assert [row["Sales"] for row in after_failure["rows"]] == [30, 40]


def test_free_plan_allows_one_google_sheet_connection(client, monkeypatch):
    client.application.config["FREE_DATASET_LIMIT"] = 3
    monkeypatch.setattr(routes_module, "fetch_google_sheet", lambda *args, **kwargs: snapshot())
    first = client.post(
        "/api/google-sheets",
        json={"url": "https://docs.google.com/spreadsheets/d/1abcdefghijklmnopqrstuvwxyzABCDE/edit"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/google-sheets",
        json={"url": "https://docs.google.com/spreadsheets/d/1abcdefghijklmnopqrstuvwxyzABCDE/edit"},
    )
    assert second.status_code == 403
    assert second.get_json()["feature"] == "google_sheet_connections"
