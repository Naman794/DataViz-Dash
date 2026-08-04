import mongomock
import pytest

from dataviz import create_app


@pytest.fixture
def app():
    mongo_client = mongomock.MongoClient()
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "MONGO_CLIENT": mongo_client,
            "MONGO_DB_NAME": "dataviz_test",
            "MAX_DATASET_ROWS": 100,
            "CHART_ROW_LIMIT": 100,
            "FREE_DATASET_LIMIT": 1,
            "FREE_DASHBOARD_LIMIT": 1,
            "FREE_CHART_LIMIT": 2,
        }
    )
    yield application
    mongo_client.close()


@pytest.fixture
def client(app):
    return app.test_client()
