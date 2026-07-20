"""Format-specific readers: turn a source file into ``list[dict]`` rows.

Bronze keeps data *as-ingested* — CSV/Excel come back as strings (leading zeros
preserved, no implicit typing), Parquet/JSON keep their native types. Typing,
validation, and cleaning happen in Silver (Phase 6).
"""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd


def _df_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    # Normalize pandas NaN/NaT to None so nulls are explicit in Bronze.
    return df.where(pd.notnull(df), None).to_dict("records")


def read_csv(data: bytes, *, delimiter: str = ",") -> list[dict[str, Any]]:
    # dtype=str + keep_default_na=False: preserve leading zeros, don't invent NaN.
    df = pd.read_csv(io.BytesIO(data), sep=delimiter, dtype=str, keep_default_na=False)
    return df.to_dict("records")


def read_json(data: bytes) -> list[dict[str, Any]]:
    payload = json.loads(data.decode("utf-8"))
    if isinstance(payload, dict):
        return payload.get("records", [])
    return payload if isinstance(payload, list) else []


def read_parquet(data: bytes) -> list[dict[str, Any]]:
    df = pd.read_parquet(io.BytesIO(data))
    return _df_to_rows(df)


def read_excel_sheet(data: bytes, *, sheet: str, skiprows: int = 1) -> list[dict[str, Any]]:
    """Read one sheet, skipping the title row above the header (human-authored mess).

    Fully-blank trailing rows are dropped. Values stay as-read (numbers may arrive
    as text) so the DQ framework can catch the quirks in Silver.
    """
    df = pd.read_excel(io.BytesIO(data), sheet_name=sheet, skiprows=skiprows,
                       engine="openpyxl", dtype=object)
    df = df.dropna(how="all")
    return _df_to_rows(df)


def read_entity(data: bytes, *, fmt: str, delimiter: str = ",", sheet: str | None = None
                ) -> list[dict[str, Any]]:
    """Dispatch to the right reader by declared format."""
    if fmt == "csv":
        return read_csv(data, delimiter=delimiter)
    if fmt == "json":
        return read_json(data)
    if fmt == "parquet":
        return read_parquet(data)
    if fmt == "xlsx":
        if not sheet:
            raise ValueError("xlsx format requires a sheet name")
        return read_excel_sheet(data, sheet=sheet)
    raise ValueError(f"Unsupported format: {fmt}")
