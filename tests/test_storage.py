import mongomock
import pandas as pd

from dataviz.storage import Store


def test_large_dataset_rows_are_inserted_in_batches(monkeypatch):
    mongo_client = mongomock.MongoClient()
    database = mongo_client.dataviz_test
    repository = Store(database)
    batch_sizes = []
    insert_many = database.dataset_rows.insert_many

    def record_batch(documents):
        batch_sizes.append(len(documents))
        return insert_many(documents)

    monkeypatch.setattr(database.dataset_rows, "insert_many", record_batch)
    dataset = repository.create_dataset(
        "owner-id", "large.csv", pd.DataFrame({"value": range(2501)})
    )

    assert dataset["row_count"] == 2501
    assert batch_sizes == [1000, 1000, 501]
    mongo_client.close()
