from dataviz.config import Config


def test_default_capacity_limits():
    assert Config.MAX_UPLOAD_MB == 50
    assert Config.MAX_CONTENT_LENGTH == 51 * 1024 * 1024
    assert Config.MAX_DATASET_ROWS == 50000
    assert Config.CHART_ROW_LIMIT == 50000
    assert Config.FREE_UPLOAD_MB == 10
    assert Config.FREE_DATASET_ROWS == 10000
    assert Config.FREE_DATASET_LIMIT == 3
    assert Config.PRO_DATASET_LIMIT == 25
