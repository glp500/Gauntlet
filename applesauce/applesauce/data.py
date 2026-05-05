from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .models import ColumnProfile, ColumnRoles, DataCard

DATE_NAME_HINTS = ("date", "time", "timestamp", "created", "updated", "month", "year")


def load_dataset(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(path, lines=suffix == ".jsonl")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported dataset type '{suffix}'. Use CSV, TSV, JSON, Excel, or Parquet.")


def clean_column_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", str(name).strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "column"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    seen: dict[str, int] = {}
    columns: list[str] = []
    for column in df.columns:
        base = clean_column_name(column)
        count = seen.get(base, 0)
        seen[base] = count + 1
        columns.append(base if count == 0 else f"{base}_{count + 1}")
    normalized = df.copy()
    normalized.columns = columns
    return normalized


def looks_datetime_like(name: str, series: pd.Series) -> bool:
    if any(hint in name.lower() for hint in DATE_NAME_HINTS):
        return True
    sample = series.dropna().astype(str).head(25)
    if sample.empty:
        return False
    dateish = sample.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").mean()
    return bool(dateish >= 0.5)


def infer_and_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    cleaned = normalize_columns(df)
    cleaned = cleaned.replace(r"^\s*$", pd.NA, regex=True)
    before = len(cleaned)
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    duplicate_rows_removed = before - len(cleaned)

    for column in cleaned.columns:
        series = cleaned[column]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            non_null_count = max(int(series.notna().sum()), 1)
            if looks_datetime_like(column, series):
                datetime = pd.to_datetime(series, errors="coerce", utc=False)
                datetime_ratio = float(datetime.notna().sum()) / non_null_count
                if datetime_ratio >= 0.85:
                    cleaned[column] = datetime
                    continue

            normalized_numeric_text = series.astype("string").str.replace(",", "", regex=False).str.replace("$", "", regex=False).str.replace("%", "", regex=False).str.strip()
            numeric = pd.to_numeric(normalized_numeric_text, errors="coerce")
            numeric_ratio = float(numeric.notna().sum()) / non_null_count
            if numeric_ratio >= 0.85:
                cleaned[column] = numeric
                continue

            lowered = series.dropna().astype(str).str.lower().str.strip()
            if not lowered.empty and lowered.isin({"true", "false", "yes", "no", "1", "0"}).mean() >= 0.95:
                cleaned[column] = lowered.map({"true": True, "yes": True, "1": True, "false": False, "no": False, "0": False})

    return cleaned, duplicate_rows_removed


def column_role(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    non_null = series.dropna()
    if non_null.empty:
        return "unknown"
    unique_ratio = non_null.nunique(dropna=True) / max(len(non_null), 1)
    if non_null.nunique(dropna=True) <= 25 or unique_ratio <= 0.2:
        return "categorical"
    return "text"


def profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    profiles: list[ColumnProfile] = []
    row_count = len(df)
    for name in df.columns:
        series = df[name]
        missing_count = int(series.isna().sum())
        samples = [str(value) for value in series.dropna().head(5).tolist()]
        profiles.append(
            ColumnProfile(
                name=name,
                dtype=str(series.dtype),
                role=column_role(series),  # type: ignore[arg-type]
                missing_count=missing_count,
                missing_percent=round((missing_count / row_count * 100) if row_count else 0, 2),
                unique_count=int(series.nunique(dropna=True)),
                sample_values=samples,
            )
        )
    return profiles


def build_data_card(source_path: Path, df: pd.DataFrame, duplicate_rows_removed: int) -> DataCard:
    missing_cells = int(df.isna().sum().sum())
    total_cells = max(int(df.shape[0] * df.shape[1]), 1)
    notes: list[str] = []
    if duplicate_rows_removed:
        notes.append(f"Removed {duplicate_rows_removed} duplicate row(s).")
    if missing_cells:
        notes.append("Missing values are retained for transparent analysis.")
    return DataCard(
        source_path=str(source_path),
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        duplicate_rows_removed=duplicate_rows_removed,
        missing_cells=missing_cells,
        missing_percent=round(missing_cells / total_cells * 100, 2),
        columns=profile_columns(df),
        notes=notes,
    )


def roles_from_card(card: DataCard) -> ColumnRoles:
    roles = ColumnRoles()
    for column in card.columns:
        getattr(roles, column.role, roles.text).append(column.name)
    return roles
