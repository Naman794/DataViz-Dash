"""MongoDB lifecycle and indexes."""

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
        database.dataset_rows.create_index(
            [("dataset_id", ASCENDING), ("position", ASCENDING)], unique=True
        )
        database.dashboards.create_index(
            [("owner_id", ASCENDING), ("updated_at", DESCENDING)]
        )
        database.activity_events.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)]
        )
        database.admin_audit.create_index([("created_at", DESCENDING)])
        database.admin_audit.create_index(
            [("target_user_id", ASCENDING), ("created_at", DESCENDING)]
        )
    except PyMongoError as exc:
        app.logger.warning(
            "MongoDB was not reachable during startup; requests will retry later: %s",
            exc,
        )


def get_database():
    return current_app.extensions["mongo_db"]
