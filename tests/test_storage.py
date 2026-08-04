import mongomock
import pandas as pd
import pytest

import dataviz.storage as storage_module
from dataviz.storage import Store
from dataviz.tabular import DataValidationError


def test_large_dataset_rows_are_stored_in_chunks():
    mongo_client = mongomock.MongoClient()
    database = mongo_client.dataviz_test
    repository = Store(database)
    dataset = repository.create_dataset(
        "owner-id", "large.csv", pd.DataFrame({"value": range(2501)})
    )

    assert dataset["row_count"] == 2501
    chunks = list(database.dataset_rows.find().sort("position", 1))
    assert [len(chunk["rows"]) for chunk in chunks] == [1000, 1000, 501]
    mongo_client.close()


def test_fifty_thousand_rows_round_trip_with_fifty_documents():
    mongo_client = mongomock.MongoClient()
    database = mongo_client.dataviz_test
    repository = Store(database)
    frame = pd.DataFrame(
        {
            "region": [f"Region {index % 25}" for index in range(50_000)],
            "value": range(50_000),
        }
    )

    created = repository.create_dataset("owner-id", "large.csv", frame)
    stored = repository.get_dataset("owner-id", created["id"])

    assert database.dataset_rows.count_documents({}) == 50
    assert repository.get_rows(stored, 100) == frame.head(100).to_dict(
        orient="records"
    )
    assert repository.get_frame(stored).equals(frame)
    mongo_client.close()


def test_failed_replacement_preserves_existing_rows(monkeypatch):
    mongo_client = mongomock.MongoClient()
    database = mongo_client.dataviz_test
    repository = Store(database)
    created = repository.create_dataset(
        "owner-id", "values.csv", pd.DataFrame({"value": [1, 2, 3]})
    )
    stored = repository.get_dataset("owner-id", created["id"])

    def fail_insert(_dataset_id, _frame):
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(repository, "_insert_rows", fail_insert)
    with pytest.raises(RuntimeError, match="simulated storage failure"):
        repository.replace_dataset(stored, pd.DataFrame({"value": [4, 5]}))

    assert repository.get_frame(stored).to_dict(orient="list") == {
        "value": [1, 2, 3]
    }
    mongo_client.close()


def test_legacy_single_row_documents_remain_readable():
    mongo_client = mongomock.MongoClient()
    database = mongo_client.dataviz_test
    repository = Store(database)
    created = repository.create_dataset(
        "owner-id", "legacy.csv", pd.DataFrame({"value": [1, 2]})
    )
    stored = repository.get_dataset("owner-id", created["id"])
    database.dataset_rows.delete_many({"dataset_id": stored["_id"]})
    database.dataset_rows.insert_many(
        [
            {"dataset_id": stored["_id"], "position": 0, "data": {"value": 1}},
            {"dataset_id": stored["_id"], "position": 1, "data": {"value": 2}},
        ]
    )

    assert repository.get_rows(stored, 10) == [{"value": 1}, {"value": 2}]
    mongo_client.close()


def test_oversized_row_is_rejected_and_partial_dataset_is_removed(monkeypatch):
    mongo_client = mongomock.MongoClient()
    database = mongo_client.dataviz_test
    repository = Store(database)
    monkeypatch.setattr(storage_module, "ROW_CHUNK_TARGET_BYTES", 100)

    with pytest.raises(DataValidationError, match="row is too large"):
        repository.create_dataset(
            "owner-id",
            "wide.csv",
            pd.DataFrame({"value": ["x" * 200]}),
        )

    assert database.datasets.count_documents({}) == 0
    assert database.dataset_rows.count_documents({}) == 0
    mongo_client.close()
