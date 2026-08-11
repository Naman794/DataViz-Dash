"""Bundled demo data and dashboard definition for first-run onboarding."""

from __future__ import annotations

import pandas as pd

SAMPLE_DATASET_NAME = "dataviz-sample-sales.csv"
SAMPLE_DASHBOARD_TITLE = "Sample sales overview"

SAMPLE_ROWS = [
    {"Date": "2026-01-08", "Region": "North", "Category": "Electronics", "Revenue": 184000, "Orders": 42, "Margin": 28.4},
    {"Date": "2026-01-19", "Region": "South", "Category": "Furniture", "Revenue": 121000, "Orders": 31, "Margin": 22.1},
    {"Date": "2026-02-05", "Region": "East", "Category": "Office Supplies", "Revenue": 76000, "Orders": 55, "Margin": 18.7},
    {"Date": "2026-02-22", "Region": "West", "Category": "Electronics", "Revenue": 213000, "Orders": 47, "Margin": 31.2},
    {"Date": "2026-03-03", "Region": "North", "Category": "Furniture", "Revenue": 148000, "Orders": 36, "Margin": 24.8},
    {"Date": "2026-03-17", "Region": "South", "Category": "Office Supplies", "Revenue": 92000, "Orders": 63, "Margin": 20.5},
    {"Date": "2026-04-09", "Region": "East", "Category": "Electronics", "Revenue": 196000, "Orders": 44, "Margin": 29.6},
    {"Date": "2026-04-24", "Region": "West", "Category": "Furniture", "Revenue": 137000, "Orders": 34, "Margin": 23.9},
    {"Date": "2026-05-06", "Region": "North", "Category": "Office Supplies", "Revenue": 87000, "Orders": 59, "Margin": 19.8},
    {"Date": "2026-05-21", "Region": "South", "Category": "Electronics", "Revenue": 225000, "Orders": 51, "Margin": 32.5},
    {"Date": "2026-06-11", "Region": "East", "Category": "Furniture", "Revenue": 156000, "Orders": 39, "Margin": 25.7},
    {"Date": "2026-06-26", "Region": "West", "Category": "Office Supplies", "Revenue": 101000, "Orders": 68, "Margin": 21.4},
]


def sample_frame() -> pd.DataFrame:
    """Return a fresh sample sales frame."""
    return pd.DataFrame(SAMPLE_ROWS)


def sample_dashboard_payload(dataset_id: str, max_charts: int = 4) -> dict:
    """Return a demo dashboard bounded by the active plan's visual limit."""
    charts = [
        {
            "id": "sample-revenue-kpi",
            "title": "Total revenue",
            "type": "kpi",
            "x": "Region",
            "y": "Revenue",
            "aggregation": "sum",
            "layout": {"x": 0, "y": 0, "w": 3, "h": 4},
        },
        {
            "id": "sample-region-bar",
            "title": "Revenue by region",
            "type": "bar",
            "x": "Region",
            "y": "Revenue",
            "aggregation": "sum",
            "sort": "descending",
            "layout": {"x": 3, "y": 0, "w": 9, "h": 7},
        },
        {
            "id": "sample-monthly-line",
            "title": "Monthly revenue",
            "type": "line",
            "x": "Date",
            "y": "Revenue",
            "aggregation": "sum",
            "date_group": "month",
            "layout": {"x": 0, "y": 7, "w": 8, "h": 7},
        },
        {
            "id": "sample-category-table",
            "title": "Category performance",
            "type": "table",
            "x": "Category",
            "y": "Revenue",
            "aggregation": "sum",
            "sort": "descending",
            "layout": {"x": 8, "y": 7, "w": 4, "h": 7},
        },
    ]
    charts = charts[: max(1, min(4, max_charts))]
    return {
        "title": SAMPLE_DASHBOARD_TITLE,
        "dataset_id": dataset_id,
        "charts": charts,
        "pages": [{"id": "overview", "title": "Overview", "charts": charts}],
        "active_page_id": "overview",
        "filters": [],
    }
