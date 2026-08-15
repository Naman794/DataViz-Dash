"""Plan definitions and entitlement resolution."""

from flask import current_app


PRICING_CATALOG = (
    {
        "name": "free",
        "label": "Free",
        "positioning": "Individual experimentation",
        "price": "₹0",
        "price_note": "forever",
        "availability": "available",
    },
    {
        "name": "pro",
        "label": "Pro",
        "positioning": "Freelancer / analyst",
        "price": "₹499",
        "price_note": "per month",
        "availability": "coming soon",
    },
    {
        "name": "business",
        "label": "Business",
        "positioning": "Teams + larger usage",
        "price": "₹1,999–₹2,999",
        "price_note": "per month",
        "availability": "planned",
    },
    {
        "name": "agency",
        "label": "Agency",
        "positioning": "Multiple clients / workspaces",
        "price": "₹4,999–₹9,999",
        "price_note": "per month",
        "availability": "planned",
    },
    {
        "name": "enterprise",
        "label": "Enterprise",
        "positioning": "SSO, private deployment, SLA",
        "price": "Custom",
        "price_note": "contact-led",
        "availability": "planned",
    },
    {
        "name": "government",
        "label": "Government",
        "positioning": "Private/on-prem deployment + support",
        "price": "Custom annual contract",
        "price_note": "contact-led",
        "availability": "planned",
    },
)


def resolve_plan(user=None) -> dict:
    """Return server-enforced limits for the current account plan."""
    plan_name = "pro" if user and user.get("plan") == "pro" else "free"
    if plan_name == "pro":
        return {
            "name": "pro",
            "label": "Pro",
            "max_upload_mb": current_app.config["MAX_UPLOAD_MB"],
            "max_dataset_rows": current_app.config["MAX_DATASET_ROWS"],
            "max_datasets": current_app.config["PRO_DATASET_LIMIT"],
            "max_dashboards": current_app.config["PRO_DASHBOARD_LIMIT"],
            "max_charts": current_app.config["PRO_CHART_LIMIT"],
            "chart_row_limit": current_app.config["CHART_ROW_LIMIT"],
            "max_storage_mb": current_app.config["PRO_STORAGE_MB"],
            "max_pages": current_app.config["PRO_PAGE_LIMIT"],
            "dashboard_exports": True,
        }

    return {
        "name": "free",
        "label": "Free",
        "max_upload_mb": min(
            current_app.config["FREE_UPLOAD_MB"],
            current_app.config["MAX_UPLOAD_MB"],
        ),
        "max_dataset_rows": min(
            current_app.config["FREE_DATASET_ROWS"],
            current_app.config["MAX_DATASET_ROWS"],
        ),
        "max_datasets": current_app.config["FREE_DATASET_LIMIT"],
        "max_dashboards": current_app.config["FREE_DASHBOARD_LIMIT"],
        "max_charts": current_app.config["FREE_CHART_LIMIT"],
        "chart_row_limit": min(
            current_app.config["FREE_CHART_ROW_LIMIT"],
            current_app.config["CHART_ROW_LIMIT"],
        ),
        "max_storage_mb": current_app.config["FREE_STORAGE_MB"],
        "max_pages": current_app.config["FREE_PAGE_LIMIT"],
        "dashboard_exports": False,
    }
