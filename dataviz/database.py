"""MongoDB lifecycle, retention metadata, and indexes."""

from datetime import datetime, timedelta, timezone

from flask import current_app
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError


def init_database(app):
    client = app.config.get("MONGO_CLIENT")
    if client is None:
        client = MongoClient(
            app.config["MONGO_URI"],
            connect=False,
            serverSelectionTimeoutMS=app.config[
                "MONGO_SERVER_SELECTION_TIMEOUT_MS"
            ],
            connectTimeoutMS=app.config["MONGO_CONNECT_TIMEOUT_MS"],
            socketTimeoutMS=app.config["MONGO_SOCKET_TIMEOUT_MS"],
        )

    database = client[app.config["MONGO_DB_NAME"]]
    app.extensions["mongo_client"] = client
    app.extensions["mongo_db"] = database

    try:
        database.users.create_index("email", unique=True)
        database.users.create_index("google_subject", unique=True, sparse=True)
        database.users.create_index(
            [("status", ASCENDING), ("plan", ASCENDING), ("created_at", DESCENDING)]
        )
        database.datasets.create_index(
            [("owner_id", ASCENDING), ("updated_at", DESCENDING)]
        )
        database.datasets.create_index("expires_at", expireAfterSeconds=0)
        database.dataset_rows.create_index(
            [("dataset_id", ASCENDING), ("position", ASCENDING)], unique=True
        )
        database.dataset_rows.create_index("expires_at", expireAfterSeconds=0)
        database.dashboards.create_index(
            [("owner_id", ASCENDING), ("updated_at", DESCENDING)]
        )
        database.dashboards.create_index("expires_at", expireAfterSeconds=0)
        database.activity_events.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)]
        )
        database.admin_audit.create_index([("created_at", DESCENDING)])
        database.admin_audit.create_index(
            [("target_user_id", ASCENDING), ("created_at", DESCENDING)]
        )
        backfill_retention_deadlines(database, app.config["DATA_RETENTION_DAYS"])
    except PyMongoError as exc:
        app.logger.warning(
            "MongoDB was not reachable during startup; requests will retry later: %s",
            exc,
        )


def get_database():
    return current_app.extensions["mongo_db"]


def backfill_retention_deadlines(database, retention_days: int):
    """Apply the retention deadline to records created before this policy."""
    period = timedelta(days=max(1, int(retention_days)))
    now = datetime.now(timezone.utc)
    for dataset in database.datasets.find(
        {"expires_at": {"$exists": False}},
        {"created_at": 1, "row_source_id": 1},
    ):
        created_at = dataset.get("created_at") or now
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        expires_at = created_at + period
        database.datasets.update_one(
            {"_id": dataset["_id"]}, {"$set": {"expires_at": expires_at}}
        )
        row_ids = list(
            {dataset["_id"], dataset.get("row_source_id", dataset["_id"])}
        )
        database.dataset_rows.update_many(
            {"dataset_id": {"$in": row_ids}},
            {"$set": {"expires_at": expires_at}},
        )
    for dashboard in database.dashboards.find(
        {"expires_at": {"$exists": False}}, {"created_at": 1}
    ):
        created_at = dashboard.get("created_at") or now
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        database.dashboards.update_one(
            {"_id": dashboard["_id"]},
            {"$set": {"expires_at": created_at + period}},
        )
