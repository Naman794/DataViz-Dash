"""MongoDB persistence for datasets and dashboards."""

from datetime import datetime, timezone

import pandas as pd
from bson import BSON, ObjectId

from .tabular import (
    DataValidationError,
    column_types,
    frame_to_records,
    records_to_frame,
)

ROW_CHUNK_SIZE = 1000
ROW_CHUNK_TARGET_BYTES = 8 * 1024 * 1024
CHUNK_INSERT_BATCH_SIZE = 4


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
            self.db.dataset_rows.delete_many({"dataset_id": dataset_id})
            self.db.datasets.delete_one({"_id": dataset_id})
            raise
        metadata["_id"] = dataset_id
        return self.serialize_dataset(metadata)

    def list_datasets(self, owner_id: str):
        documents = self.db.datasets.find({"owner_id": owner_id}).sort("updated_at", -1)
        return [self.serialize_dataset(document) for document in documents]

    def count_datasets(self, owner_id: str) -> int:
        return self.db.datasets.count_documents({"owner_id": owner_id})

    def get_dataset(self, owner_id: str, dataset_id: str):
        object_id = self._object_id(dataset_id)
        if object_id is None:
            return None
        return self.db.datasets.find_one({"_id": object_id, "owner_id": owner_id})

    def get_frame(self, dataset) -> pd.DataFrame:
        rows = self._read_rows(dataset)
        return records_to_frame(rows, dataset["columns"])

    def get_rows(self, dataset, limit: int):
        return self._read_rows(dataset, limit=limit)

    def replace_dataset(self, dataset, frame: pd.DataFrame):
        dataset_id = dataset["_id"]
        old_row_source_id = dataset.get("row_source_id", dataset_id)
        new_row_source_id = ObjectId()
        try:
            self._insert_rows(new_row_source_id, frame)
        except Exception:
            self.db.dataset_rows.delete_many({"dataset_id": new_row_source_id})
            raise
        now = utc_now()
        updates = {
            "columns": list(frame.columns),
            "column_types": column_types(frame),
            "row_count": len(frame),
            "row_source_id": new_row_source_id,
            "updated_at": now,
        }
        try:
            self.db.datasets.update_one({"_id": dataset_id}, {"$set": updates})
        except Exception:
            self.db.dataset_rows.delete_many({"dataset_id": new_row_source_id})
            raise
        dataset.update(updates)
        self.db.dataset_rows.delete_many({"dataset_id": old_row_source_id})
        return self.serialize_dataset(dataset)

    def delete_dataset(self, owner_id: str, dataset_id: str):
        dataset = self.get_dataset(owner_id, dataset_id)
        if dataset is None:
            return False
        row_source_id = dataset.get("row_source_id", dataset["_id"])
        self.db.dataset_rows.delete_many(
            {"dataset_id": {"$in": list({dataset["_id"], row_source_id})}}
        )
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

    def count_dashboards(self, owner_id: str) -> int:
        return self.db.dashboards.count_documents({"owner_id": owner_id})

    def create_user(self, email: str, password_hash: str):
        now = utc_now()
        document = {
            "email": email,
            "password_hash": password_hash,
            "plan": "free",
            "created_at": now,
            "updated_at": now,
        }
        result = self.db.users.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def get_user(self, user_id: str):
        object_id = self._object_id(user_id)
        if object_id is None:
            return None
        return self.db.users.find_one({"_id": object_id})

    def get_user_by_email(self, email: str):
        return self.db.users.find_one({"email": email})

    def claim_workspace(self, previous_owner_id: str, user_id: str):
        if not previous_owner_id or previous_owner_id == user_id:
            return
        self.db.datasets.update_many(
            {"owner_id": previous_owner_id}, {"$set": {"owner_id": user_id}}
        )
        self.db.dashboards.update_many(
            {"owner_id": previous_owner_id}, {"$set": {"owner_id": user_id}}
        )

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
        pending_documents = []
        for start in range(0, len(frame), ROW_CHUNK_SIZE):
            records = frame_to_records(frame.iloc[start : start + ROW_CHUNK_SIZE])
            chunk = []
            chunk_size = 0
            for offset, record in enumerate(records):
                record_size = len(BSON.encode({"data": record}))
                if record_size > ROW_CHUNK_TARGET_BYTES:
                    raise DataValidationError(
                        "A spreadsheet row is too large to store safely. "
                        "Split very large cell contents into smaller rows or columns."
                    )
                if chunk and chunk_size + record_size > ROW_CHUNK_TARGET_BYTES:
                    pending_documents.append(
                        {
                            "dataset_id": dataset_id,
                            "position": start + offset - len(chunk),
                            "rows": chunk,
                        }
                    )
                    if len(pending_documents) >= CHUNK_INSERT_BATCH_SIZE:
                        self.db.dataset_rows.insert_many(pending_documents)
                        pending_documents = []
                    chunk = []
                    chunk_size = 0
                chunk.append(record)
                chunk_size += record_size
            if chunk:
                pending_documents.append(
                    {
                        "dataset_id": dataset_id,
                        "position": start + len(records) - len(chunk),
                        "rows": chunk,
                    }
                )
                if len(pending_documents) >= CHUNK_INSERT_BATCH_SIZE:
                    self.db.dataset_rows.insert_many(pending_documents)
                    pending_documents = []
        if pending_documents:
            self.db.dataset_rows.insert_many(pending_documents)

    def _read_rows(self, dataset, limit: int | None = None):
        row_source_id = dataset.get("row_source_id", dataset["_id"])
        documents = self.db.dataset_rows.find(
            {"dataset_id": row_source_id},
            {"_id": 0, "data": 1, "rows": 1},
        ).sort("position", 1)
        rows = []
        for document in documents:
            # The single-row shape keeps datasets created before V 0.1.1 readable.
            document_rows = document.get("rows")
            if document_rows is None and "data" in document:
                document_rows = [document["data"]]
            rows.extend(document_rows or [])
            if limit is not None and len(rows) >= limit:
                return rows[:limit]
        return rows

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
