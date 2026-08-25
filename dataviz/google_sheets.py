"""Safe, bounded imports from publicly viewable Google Sheets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import pandas as pd
import requests

from .tabular import DataLimitError, DataValidationError, parse_csv_bytes

GOOGLE_SHEETS_HOST = "docs.google.com"
SPREADSHEET_PATH = re.compile(r"^/spreadsheets/d/([A-Za-z0-9_-]{20,})")
DEFAULT_TIMEOUT_SECONDS = (5, 20)
CHUNK_SIZE = 64 * 1024


class GoogleSheetError(DataValidationError):
    """Raised when a Google Sheet cannot be validated or downloaded."""


@dataclass(frozen=True)
class GoogleSheetReference:
    spreadsheet_id: str
    sheet_gid: str

    @property
    def canonical_url(self) -> str:
        return (
            f"https://{GOOGLE_SHEETS_HOST}/spreadsheets/d/"
            f"{self.spreadsheet_id}/edit#gid={self.sheet_gid}"
        )

    @property
    def csv_url(self) -> str:
        query = urlencode({"tqx": "out:csv", "gid": self.sheet_gid})
        return urlunsplit(
            (
                "https",
                GOOGLE_SHEETS_HOST,
                f"/spreadsheets/d/{self.spreadsheet_id}/gviz/tq",
                query,
                "",
            )
        )


@dataclass(frozen=True)
class GoogleSheetSnapshot:
    frame: pd.DataFrame
    reference: GoogleSheetReference
    source_size_bytes: int
    filename: str


def parse_google_sheet_url(value: str) -> GoogleSheetReference:
    """Accept only normal HTTPS Google Sheets URLs and extract their worksheet gid."""
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError as exc:
        raise GoogleSheetError("Enter a valid Google Sheets link.") from exc

    if parsed.scheme != "https" or parsed.hostname != GOOGLE_SHEETS_HOST:
        raise GoogleSheetError(
            "Use an HTTPS link from docs.google.com/spreadsheets."
        )
    match = SPREADSHEET_PATH.match(parsed.path)
    if match is None:
        raise GoogleSheetError("Enter a standard Google Sheets sharing link.")

    fragment_values = parse_qs(parsed.fragment)
    query_values = parse_qs(parsed.query)
    gid = (fragment_values.get("gid") or query_values.get("gid") or ["0"])[0]
    if not str(gid).isdigit():
        raise GoogleSheetError("The worksheet identifier in this link is invalid.")
    return GoogleSheetReference(match.group(1), str(gid))


def fetch_google_sheet(
    source_url: str,
    max_rows: int,
    max_bytes: int,
    *,
    http_get=requests.get,
) -> GoogleSheetSnapshot:
    """Download a public worksheet as CSV without fetching a user-controlled host."""
    reference = parse_google_sheet_url(source_url)
    try:
        response = http_get(
            reference.csv_url,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            stream=True,
            allow_redirects=False,
            headers={"User-Agent": "DataViz-Dash/0.3 Google-Sheets-Connector"},
        )
    except requests.RequestException as exc:
        raise GoogleSheetError(
            "Google Sheets could not be reached. Try again in a moment."
        ) from exc

    if 300 <= response.status_code < 400:
        raise GoogleSheetError("Google redirected this sheet unexpectedly.")
    if response.status_code in {401, 403, 404}:
        raise GoogleSheetError(
            "This sheet is not publicly viewable. Set General access to "
            '"Anyone with the link" and try again.'
        )
    if response.status_code != 200:
        raise GoogleSheetError(
            f"Google Sheets returned an unexpected response ({response.status_code})."
        )

    payload = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            payload.extend(chunk)
            if len(payload) > max_bytes:
                raise GoogleSheetError(
                    f"The sheet is too large. Maximum source size is "
                    f"{max_bytes // (1024 * 1024)} MB."
                )
    finally:
        response.close()

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" in content_type or bytes(payload).lstrip().startswith(b"<!DOCTYPE"):
        raise GoogleSheetError(
            "Google returned a web page instead of sheet data. Check the sharing access."
        )
    try:
        frame = parse_csv_bytes(
            bytes(payload), max_rows=max_rows, max_bytes=max_bytes
        )
    except DataLimitError:
        raise
    except DataValidationError as exc:
        raise GoogleSheetError(str(exc)) from exc
    filename = f"Google Sheet {reference.spreadsheet_id[:8]} (tab {reference.sheet_gid}).csv"
    return GoogleSheetSnapshot(frame, reference, len(payload), filename)
