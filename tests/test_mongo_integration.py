"""Optional tests against a real MongoDB server.

CI supplies TEST_MONGO_URI. Local runs skip this module unless the same variable is set.
"""

import os
from uuid import uuid4

import pandas as pd
import pytest
from pymongo import MongoClient

from dataviz.database import init_database
from dataviz.storage import Store

TEST_MONGO_URI = os.getenv("TEST_MONGO_URI")
pytestmark = pytest.mark.skipif(
    not TEST_MONGO_URI,
    reason="TEST_MONGO_URI is not configured",
)


def test_real_mongodb_indexes_and_fifty_thousand_row_round_trip():
    database_name = f"dataviz_integration_{uuid4().hex}"
    client = MongoClient(TEST_MONGO_URI, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")

        class TestApp:
            config = {
                "MONGO_CLIENT": client,
                "MONGO_URI": TEST_MONGO_URI,
                "MONGO_DB_NAME": database_name,
            }
            extensions = {}

        app = TestApp()
        init_database(app)
        database = app.extensions["mongo_db"]
        repository = Store(database)
        frame = pd.DataFrame(
            {
                "region": [f"Region {index % 25}" for index in range(50_000)],
                "value": range(50_000),
            }
        )

        created = repository.create_dataset("integration-owner", "large.csv", frame)
        stored = repository.get_dataset("integration-owner", created["id"])

        assert database.dataset_rows.count_documents({}) == 50
        assert repository.get_rows(stored, 100) == frame.head(100).to_dict(
            orient="records"
        )
        assert repository.get_frame(stored).equals(frame)
        assert database.datasets.index_information()
        assert database.dataset_rows.index_information()
    finally:
        client.drop_database(database_name)
        client.close()
