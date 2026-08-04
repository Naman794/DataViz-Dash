from io import BytesIO

import pandas as pd
import pytest
from werkzeug.datastructures import FileStorage

from dataviz.tabular import DataValidationError, clean_frame, parse_upload


def upload(name, content):
    return FileStorage(stream=BytesIO(content), filename=name)


def test_parse_csv_normalizes_duplicate_and_blank_columns():
    frame = parse_upload(upload("sample.csv", b"Name,Name,\nA,1,x\n"), max_rows=10)
    assert list(frame.columns) == ["Name", "Name_2", "Column 3"]
    assert len(frame) == 1


def test_parse_rejects_unknown_files():
    with pytest.raises(DataValidationError, match="CSV, XLS, or XLSX"):
        parse_upload(upload("sample.txt", b"hello"), max_rows=10)


def test_parse_excel_file():
    output = BytesIO()
    pd.DataFrame({"Month": ["January"], "Revenue": [1250]}).to_excel(
        output, index=False
    )
    frame = parse_upload(upload("report.xlsx", output.getvalue()), max_rows=10)
    assert frame.to_dict(orient="records") == [{"Month": "January", "Revenue": 1250}]


def test_parse_enforces_row_limit():
    with pytest.raises(DataValidationError, match="up to 2 rows"):
        parse_upload(upload("sample.csv", b"Value\n1\n2\n3\n"), max_rows=2)


def test_parse_accepts_exactly_fifty_thousand_csv_rows():
    content = b"Region,Value\n" + b"North,1\n" * 50_000

    frame = parse_upload(upload("large.csv", content), max_rows=50_000)

    assert len(frame) == 50_000


def test_parse_enforces_file_size_limit():
    with pytest.raises(DataValidationError, match="Maximum size is 1 MB"):
        parse_upload(
            upload("sample.csv", b"Value\n" + (b"1\n" * 600_000)),
            max_rows=1_000_000,
            max_bytes=1024 * 1024,
        )


def test_clean_frame_applies_selected_mvp_operations():
    frame = pd.DataFrame(
        [
            {"Region": "North", "Sales": 10, "Notes": None},
            {"Region": "North", "Sales": 10, "Notes": None},
            {"Region": "South", "Sales": None, "Notes": "late"},
            {"Region": None, "Sales": None, "Notes": None},
        ]
    )
    cleaned, summary = clean_frame(
        frame,
        {
            "rename": {"Sales": "Revenue"},
            "remove_columns": ["Notes"],
            "remove_duplicates": True,
            "remove_empty_rows": True,
            "missing": {
                "strategy": "fill",
                "columns": ["Revenue"],
                "value": 0,
            },
        },
    )

    assert list(cleaned.columns) == ["Region", "Revenue"]
    assert len(cleaned) == 2
    assert cleaned.iloc[1]["Revenue"] == 0
    assert summary == {
        "rows_removed": 2,
        "columns_removed": 1,
        "rows_remaining": 2,
        "columns_remaining": 2,
    }


def test_clean_frame_prevents_removing_every_column():
    with pytest.raises(DataValidationError, match="At least one column"):
        clean_frame(pd.DataFrame({"Only": [1]}), {"remove_columns": ["Only"]})


def test_clean_frame_requires_a_missing_value_column():
    with pytest.raises(DataValidationError, match="at least one"):
        clean_frame(
            pd.DataFrame({"Value": [None]}),
            {"missing": {"strategy": "drop", "columns": []}},
        )
