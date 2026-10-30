"""Excel/CSV parsing with pandas. Supports multi-sheet workbooks."""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def _df_to_text(df: pd.DataFrame, name: str) -> str:
    buf = [f"### Sheet: {name}"]
    try:
        buf.append(df.fillna("").astype(str).to_csv(index=False))
    except Exception:
        buf.append(str(df))
    return "\n".join(buf)


def extract_spreadsheet(path: str, engine: str = "openpyxl") -> tuple[str, dict[str, Any]]:
    sheets: dict[str, Any] = {}
    parts: list[str] = []
    xl = pd.ExcelFile(path, engine=engine)
    for name in xl.sheet_names:
        try:
            df = xl.parse(name)
        except Exception as e:
            log.warning("sheet parse failed %s: %s", name, e)
            continue
        sheets[name] = {
            "columns": [str(c) for c in df.columns],
            "rows": df.fillna("").astype(str).values.tolist()[:5000],
        }
        parts.append(_df_to_text(df, name))
    return "\n\n".join(parts), sheets


def extract_csv(path: str) -> tuple[str, list[list[str]]]:
    # Try utf-8 then fallback to latin-1
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Unable to decode CSV")
    text = df.fillna("").astype(str).to_csv(index=False)
    rows = df.fillna("").astype(str).values.tolist()[:5000]
    return text, rows
