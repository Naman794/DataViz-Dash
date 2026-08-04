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
            serverSelectionTimeoutMS=3000,
        )

    database = client[app.config["MONGO_DB_NAME"]]
    app.extensions["mongo_client"] = client
    app.extensions["mongo_db"] = database

    try:
        database.datasets.create_index(
            [("owner_id", ASCENDING), ("updated_at", DESCENDING)]
        )
        database.dataset_rows.create_index(
            [("dataset_id", ASCENDING), ("position", ASCENDING)], unique=True
        )
        database.dashboards.create_index(
            [("owner_id", ASCENDING), ("updated_at", DESCENDING)]
        )
    except PyMongoError:
        app.logger.warning(
            "MongoDB was not reachable during startup; requests will retry later."
        )


def get_database():
    return current_app.extensions["mongo_db"]
