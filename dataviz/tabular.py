"""Tabular file parsing, validation, and cleaning."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}


class DataValidationError(ValueError):
    """Raised when uploaded data or a cleaning request is invalid."""


class DataLimitError(DataValidationError):
    """Raised when an upload exceeds a configurable capacity entitlement."""

    def __init__(self, message: str, feature: str):
        super().__init__(message)
        self.feature = feature


def parse_upload(
    upload, max_rows: int, max_bytes: int | None = None
) -> pd.DataFrame:
    filename = upload.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DataValidationError("Upload a CSV, XLS, or XLSX file.")

    payload = upload.read()
    if not payload:
        raise DataValidationError("The uploaded file is empty.")
    if max_bytes is not None and len(payload) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise DataLimitError(
            f"File is too large. Maximum size is {max_mb} MB.", "upload_size"
        )

    try:
        if extension == ".csv":
            frame = _parse_csv_payload(payload, max_rows)
        else:
            frame = pd.read_excel(BytesIO(payload), nrows=max_rows + 1)
    except Exception as exc:
        raise DataValidationError(
            "The file could not be read. Check that it is a valid spreadsheet."
        ) from exc

    if len(frame) > max_rows:
        raise DataLimitError(
            f"This workspace supports up to {max_rows:,} rows per dataset.",
            "dataset_rows",
        )
    if frame.empty and len(frame.columns) == 0:
        raise DataValidationError("The file does not contain a table.")

    frame.columns = _unique_column_names(frame.columns)
    return frame.reset_index(drop=True)


def parse_csv_bytes(
    payload: bytes, max_rows: int, max_bytes: int | None = None
) -> pd.DataFrame:
    """Parse a bounded CSV payload from a trusted connector transport."""
    if not payload:
        raise DataValidationError("The sheet does not contain any data.")
    if max_bytes is not None and len(payload) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise DataLimitError(
            f"The sheet is too large. Maximum source size is {max_mb} MB.",
            "upload_size",
        )
    try:
        frame = _parse_csv_payload(payload, max_rows)
    except Exception as exc:
        raise DataValidationError(
            "The sheet data could not be read as a table."
        ) from exc
    if len(frame) > max_rows:
        raise DataLimitError(
            f"This workspace supports up to {max_rows:,} rows per dataset.",
            "dataset_rows",
        )
    if frame.empty and len(frame.columns) == 0:
        raise DataValidationError("The sheet does not contain a table.")
    frame.columns = _unique_column_names(frame.columns)
    return frame.reset_index(drop=True)


def _parse_csv_payload(payload: bytes, max_rows: int) -> pd.DataFrame:
    return pd.read_csv(BytesIO(payload), nrows=max_rows + 1)


def clean_frame(frame: pd.DataFrame, operations: dict) -> tuple[pd.DataFrame, dict]:
    frame = frame.copy()
    original_rows = len(frame)
    original_columns = len(frame.columns)

    rename = operations.get("rename") or {}
    if not isinstance(rename, dict):
        raise DataValidationError("Column rename rules must be an object.")

    rename_rules = {}
    for source, target in rename.items():
        if source not in frame.columns:
            raise DataValidationError(f'Column "{source}" does not exist.')
        cleaned_target = str(target).strip()
        if not cleaned_target:
            raise DataValidationError("New column names cannot be blank.")
        rename_rules[source] = cleaned_target

    resulting_names = [rename_rules.get(column, column) for column in frame.columns]
    if len(resulting_names) != len(set(resulting_names)):
        raise DataValidationError("Column names must be unique after renaming.")
    frame = frame.rename(columns=rename_rules)

    remove_columns = operations.get("remove_columns") or []
    if not isinstance(remove_columns, list):
        raise DataValidationError("Removed columns must be provided as a list.")
    unknown_removed = sorted(set(remove_columns) - set(frame.columns))
    if unknown_removed:
        raise DataValidationError(
            f"Unknown columns selected for removal: {', '.join(unknown_removed)}."
        )
    if remove_columns and len(remove_columns) == len(frame.columns):
        raise DataValidationError("At least one column must remain in the dataset.")
    frame = frame.drop(columns=remove_columns)

    if operations.get("remove_empty_rows", True):
        frame = frame.dropna(how="all")

    missing = operations.get("missing") or {"strategy": "none"}
    strategy = missing.get("strategy", "none")
    selected_columns = missing.get("columns")
    if selected_columns is None:
        selected_columns = list(frame.columns)
    if not selected_columns and strategy != "none":
        raise DataValidationError("Select at least one missing-value column.")
    unknown_missing = sorted(set(selected_columns) - set(frame.columns))
    if unknown_missing:
        raise DataValidationError(
            f"Unknown missing-value columns: {', '.join(unknown_missing)}."
        )

    if strategy == "drop":
        frame = frame.dropna(subset=selected_columns)
    elif strategy == "fill":
        value = missing.get("value", "")
        frame.loc[:, selected_columns] = frame[selected_columns].fillna(value)
    elif strategy != "none":
        raise DataValidationError("Unsupported missing-value strategy.")

    if operations.get("remove_duplicates"):
        frame = frame.drop_duplicates()

    frame = frame.reset_index(drop=True)
    summary = {
        "rows_removed": original_rows - len(frame),
        "columns_removed": original_columns - len(frame.columns),
        "rows_remaining": len(frame),
        "columns_remaining": len(frame.columns),
    }
    return frame, summary


def frame_to_records(frame: pd.DataFrame) -> list[dict]:
    safe_frame = frame.replace([np.inf, -np.inf], np.nan)
    records = []
    for raw_record in safe_frame.to_dict(orient="records"):
        record = {}
        for key, value in raw_record.items():
            if pd.isna(value):
                value = None
            elif isinstance(value, (pd.Timestamp, pd.Timedelta)):
                value = str(value)
            elif isinstance(value, np.generic):
                value = value.item()
            record[str(key)] = value
        records.append(record)
    return records


def records_to_frame(records: list[dict], columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(records, columns=columns)


def column_types(frame: pd.DataFrame) -> dict[str, str]:
    types = {}
    for column in frame.columns:
        if pd.api.types.is_numeric_dtype(frame[column]):
            types[column] = "number"
        elif pd.api.types.is_datetime64_any_dtype(frame[column]):
            types[column] = "date"
        else:
            types[column] = "text"
    return types


def _unique_column_names(columns) -> list[str]:
    names = []
    counts = {}
    for index, raw_name in enumerate(columns, start=1):
        base = str(raw_name).strip()
        if not base or base.startswith("Unnamed:"):
            base = f"Column {index}"
        duplicate_suffix = re.fullmatch(r"(.+)\.(\d+)", base)
        if duplicate_suffix and duplicate_suffix.group(1) in counts:
            base = duplicate_suffix.group(1)
        count = counts.get(base, 0) + 1
        counts[base] = count
        names.append(base if count == 1 else f"{base}_{count}")
    return names
