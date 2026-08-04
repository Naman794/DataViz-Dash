"""MongoDB persistence for datasets and dashboards."""

from datetime import datetime, timezone

import pandas as pd
from bson import ObjectId

from .tabular import column_types, frame_to_records, records_to_frame


def utc_now():
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, database):
        self.db = database

    def create_dataset(self, owner_id: str, filename: str, frame: pd.DataFrame):
        now = utc_now()
        metadata = {
            "owner_id": owner_id,
            "name": filename,
            "columns": list(frame.columns),
            "column_types": column_types(frame),
            "row_count": len(frame),
            "created_at": now,
            "updated_at": now,
        }
        result = self.db.datasets.insert_one(metadata)
        dataset_id = result.inserted_id
        try:
            self._insert_rows(dataset_id, frame)
        except Exception:
            self.db.datasets.delete_one({"_id": dataset_id})
            raise
        metadata["_id"] = dataset_id
        return self.serialize_dataset(metadata)

    def list_datasets(self, owner_id: str):
        documents = self.db.datasets.find({"owner_id": owner_id}).sort("updated_at", -1)
        return [self.serialize_dataset(document) for document in documents]

    def get_dataset(self, owner_id: str, dataset_id: str):
        object_id = self._object_id(dataset_id)
        if object_id is None:
            return None
        return self.db.datasets.find_one({"_id": object_id, "owner_id": owner_id})

    def get_frame(self, dataset) -> pd.DataFrame:
        row_documents = self.db.dataset_rows.find(
            {"dataset_id": dataset["_id"]}, {"data": 1}
        ).sort("position", 1)
        rows = [document["data"] for document in row_documents]
        return records_to_frame(rows, dataset["columns"])

    def get_rows(self, dataset, limit: int):
        documents = (
            self.db.dataset_rows.find(
                {"dataset_id": dataset["_id"]}, {"_id": 0, "data": 1}
            )
            .sort("position", 1)
            .limit(limit)
        )
        return [document["data"] for document in documents]

    def replace_dataset(self, dataset, frame: pd.DataFrame):
        dataset_id = dataset["_id"]
        self.db.dataset_rows.delete_many({"dataset_id": dataset_id})
        self._insert_rows(dataset_id, frame)
        now = utc_now()
        updates = {
            "columns": list(frame.columns),
            "column_types": column_types(frame),
            "row_count": len(frame),
            "updated_at": now,
        }
        self.db.datasets.update_one({"_id": dataset_id}, {"$set": updates})
        dataset.update(updates)
        return self.serialize_dataset(dataset)

    def delete_dataset(self, owner_id: str, dataset_id: str):
        dataset = self.get_dataset(owner_id, dataset_id)
        if dataset is None:
            return False
        self.db.dataset_rows.delete_many({"dataset_id": dataset["_id"]})
        self.db.dashboards.delete_many({"owner_id": owner_id, "dataset_id": dataset_id})
        self.db.datasets.delete_one({"_id": dataset["_id"]})
        return True

    def create_dashboard(self, owner_id: str, payload: dict):
        now = utc_now()
        document = {
            "owner_id": owner_id,
            "title": payload["title"],
            "dataset_id": payload["dataset_id"],
            "charts": payload["charts"],
            "created_at": now,
            "updated_at": now,
        }
        result = self.db.dashboards.insert_one(document)
        document["_id"] = result.inserted_id
        return self.serialize_dashboard(document)

    def update_dashboard(self, owner_id: str, dashboard_id: str, payload: dict):
        object_id = self._object_id(dashboard_id)
        if object_id is None:
            return None
        updates = {
            "title": payload["title"],
            "dataset_id": payload["dataset_id"],
            "charts": payload["charts"],
            "updated_at": utc_now(),
        }
        result = self.db.dashboards.find_one_and_update(
            {"_id": object_id, "owner_id": owner_id},
            {"$set": updates},
            return_document=True,
        )
        return self.serialize_dashboard(result) if result else None

    def list_dashboards(self, owner_id: str):
        documents = self.db.dashboards.find({"owner_id": owner_id}).sort(
            "updated_at", -1
        )
        return [self.serialize_dashboard(document) for document in documents]

    def get_dashboard(self, owner_id: str, dashboard_id: str):
        object_id = self._object_id(dashboard_id)
        if object_id is None:
            return None
        document = self.db.dashboards.find_one({"_id": object_id, "owner_id": owner_id})
        return self.serialize_dashboard(document) if document else None

    def delete_dashboard(self, owner_id: str, dashboard_id: str):
        object_id = self._object_id(dashboard_id)
        if object_id is None:
            return False
        result = self.db.dashboards.delete_one({"_id": object_id, "owner_id": owner_id})
        return result.deleted_count == 1

    def _insert_rows(self, dataset_id: ObjectId, frame: pd.DataFrame):
        records = frame_to_records(frame)
        if records:
            self.db.dataset_rows.insert_many(
                [
                    {"dataset_id": dataset_id, "position": index, "data": record}
                    for index, record in enumerate(records)
                ]
            )

    @staticmethod
    def serialize_dataset(document):
        return {
            "id": str(document["_id"]),
            "name": document["name"],
            "columns": document["columns"],
            "column_types": document.get("column_types", {}),
            "row_count": document["row_count"],
            "created_at": document["created_at"].isoformat(),
            "updated_at": document["updated_at"].isoformat(),
        }

    @staticmethod
    def serialize_dashboard(document):
        return {
            "id": str(document["_id"]),
            "title": document["title"],
            "dataset_id": document["dataset_id"],
            "charts": document.get("charts", []),
            "created_at": document["created_at"].isoformat(),
            "updated_at": document["updated_at"].isoformat(),
        }

    @staticmethod
    def _object_id(value):
        try:
            return ObjectId(value)
        except (TypeError, ValueError):
            return None
