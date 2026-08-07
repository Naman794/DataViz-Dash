"""MongoDB persistence for workspaces, accounts, and administration."""

import re
from datetime import datetime, timezone

import pandas as pd
from bson import BSON, ObjectId
from bson.errors import InvalidId

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
            "pages": payload.get("pages", []),
            "active_page_id": payload.get("active_page_id"),
            "filters": payload.get("filters", []),
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
            "pages": payload.get("pages", []),
            "active_page_id": payload.get("active_page_id"),
            "filters": payload.get("filters", []),
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
            "status": "active",
            "login_count": 0,
            "last_login_at": None,
            "last_activity_at": now,
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

    def record_login(self, user_id: str, event_type: str = "account.login"):
        object_id = self._object_id(user_id)
        if object_id is None:
            return False
        now = utc_now()
        result = self.db.users.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "last_login_at": now,
                    "last_activity_at": now,
                    "updated_at": now,
                },
                "$inc": {"login_count": 1},
            },
        )
        if not result.matched_count:
            return False
        self.db.activity_events.insert_one(
            {"user_id": user_id, "event_type": event_type, "details": {}, "created_at": now}
        )
        return True

    def record_activity(self, user_id: str, event_type: str, details: dict | None = None):
        object_id = self._object_id(user_id)
        if object_id is None:
            return False
        now = utc_now()
        result = self.db.users.update_one(
            {"_id": object_id},
            {"$set": {"last_activity_at": now, "updated_at": now}},
        )
        if not result.matched_count:
            return False
        self.db.activity_events.insert_one(
            {
                "user_id": user_id,
                "event_type": event_type,
                "details": details or {},
                "created_at": now,
            }
        )
        return True

    def admin_summary(self):
        return {
            "users": self.db.users.count_documents({}),
            "pro_users": self.db.users.count_documents({"plan": "pro"}),
            "active_users": self.db.users.count_documents(
                {"status": {"$ne": "suspended"}}
            ),
            "suspended_users": self.db.users.count_documents(
                {"status": "suspended"}
            ),
            "datasets": self.db.datasets.count_documents({}),
            "dashboards": self.db.dashboards.count_documents({}),
            "rows": sum(
                document.get("row_count", 0)
                for document in self.db.datasets.find({}, {"row_count": 1})
            ),
        }

    def list_users(
        self,
        search: str = "",
        plan: str = "",
        status: str = "",
        limit: int = 50,
        skip: int = 0,
    ):
        query = self._user_query(search, plan, status)
        users = list(
            self.db.users.find(query)
            .sort("created_at", -1)
            .skip(max(0, skip))
            .limit(limit)
        )
        return [self._admin_user(document) for document in users]

    def count_users(self, search: str = "", plan: str = "", status: str = ""):
        return self.db.users.count_documents(self._user_query(search, plan, status))

    def update_user_plan(self, user_id: str, plan: str):
        object_id = self._object_id(user_id)
        if object_id is None or plan not in {"free", "pro"}:
            return None
        now = utc_now()
        return self.db.users.find_one_and_update(
            {"_id": object_id},
            {"$set": {"plan": plan, "updated_at": now}},
            return_document=True,
        )

    def update_user_status(self, user_id: str, status: str):
        object_id = self._object_id(user_id)
        if object_id is None or status not in {"active", "suspended"}:
            return None
        now = utc_now()
        return self.db.users.find_one_and_update(
            {"_id": object_id},
            {"$set": {"status": status, "updated_at": now}},
            return_document=True,
        )

    def record_admin_action(
        self,
        admin_user,
        target_user,
        action: str,
        previous_value: str,
        new_value: str,
    ):
        self.db.admin_audit.insert_one(
            {
                "admin_user_id": str(admin_user["_id"]),
                "admin_email": admin_user["email"],
                "target_user_id": str(target_user["_id"]),
                "target_email": target_user["email"],
                "action": action,
                "previous_value": previous_value,
                "new_value": new_value,
                "created_at": utc_now(),
            }
        )

    def recent_activity(self, limit: int = 30):
        events = list(self.db.activity_events.find().sort("created_at", -1).limit(limit))
        return self._with_activity_emails(events)

    def recent_admin_actions(self, limit: int = 20):
        return list(self.db.admin_audit.find().sort("created_at", -1).limit(limit))

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

    def _admin_user(self, document):
        user_id = str(document["_id"])
        datasets = list(
            self.db.datasets.find({"owner_id": user_id}, {"row_count": 1})
        )
        return {
            "id": user_id,
            "email": document["email"],
            "plan": "pro" if document.get("plan") == "pro" else "free",
            "status": (
                "suspended" if document.get("status") == "suspended" else "active"
            ),
            "login_count": document.get("login_count", 0),
            "last_login_at": document.get("last_login_at"),
            "last_activity_at": document.get("last_activity_at"),
            "created_at": document.get("created_at"),
            "dataset_count": len(datasets),
            "dashboard_count": self.db.dashboards.count_documents(
                {"owner_id": user_id}
            ),
            "row_count": sum(dataset.get("row_count", 0) for dataset in datasets),
        }

    @staticmethod
    def _user_query(search: str, plan: str, status: str):
        query = {}
        if search:
            query["email"] = {"$regex": re.escape(search), "$options": "i"}
        if plan in {"free", "pro"}:
            query["plan"] = plan
        if status == "suspended":
            query["status"] = "suspended"
        elif status == "active":
            query["status"] = {"$ne": "suspended"}
        return query

    def _with_activity_emails(self, events):
        user_ids = {event.get("user_id") for event in events if event.get("user_id")}
        object_ids = [self._object_id(user_id) for user_id in user_ids]
        emails = {
            str(user["_id"]): user["email"]
            for user in self.db.users.find(
                {"_id": {"$in": [value for value in object_ids if value]}},
                {"email": 1},
            )
        }
        for event in events:
            event["email"] = emails.get(event.get("user_id"), "Unknown account")
        return events

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
            "pages": document.get("pages", []),
            "active_page_id": document.get("active_page_id"),
            "filters": document.get("filters", []),
            "created_at": document["created_at"].isoformat(),
            "updated_at": document["updated_at"].isoformat(),
        }

    @staticmethod
    def _object_id(value):
        try:
            return ObjectId(value)
        except (InvalidId, TypeError, ValueError):
            return None
