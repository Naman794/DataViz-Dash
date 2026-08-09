from dataviz.config import Config


def test_default_capacity_limits():
    assert Config.MAX_UPLOAD_MB == 100
    assert Config.MAX_CONTENT_LENGTH == 101 * 1024 * 1024
    assert Config.MAX_DATASET_ROWS == 100000
    assert Config.CHART_ROW_LIMIT == 100000
    assert Config.FREE_UPLOAD_MB == 50
    assert Config.FREE_DATASET_ROWS == 100000
    assert Config.FREE_CHART_ROW_LIMIT == 50000
    assert Config.FREE_STORAGE_MB == 150
    assert Config.FREE_PAGE_LIMIT == 3
    assert Config.FREE_DATASET_LIMIT == 3
    assert Config.PRO_DATASET_LIMIT == 25
    assert Config.PRO_CHART_LIMIT == 12
    assert Config.PRO_STORAGE_MB == 5120
    assert Config.PRO_PAGE_LIMIT == 20
    assert Config.MONGO_SERVER_SELECTION_TIMEOUT_MS == 5000
    assert Config.MONGO_CONNECT_TIMEOUT_MS == 5000
    assert Config.MONGO_SOCKET_TIMEOUT_MS == 20000
