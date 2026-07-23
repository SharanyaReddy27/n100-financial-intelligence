from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "output"

CAPITAL_ALLOCATION_FILE = OUTPUT_DIR / "capital_allocation.csv"
CASHFLOW_INTELLIGENCE_FILE = OUTPUT_DIR / "cashflow_intelligence.xlsx"

PATTERN_CHANGES_FILE = OUTPUT_DIR / "pattern_changes.csv"
PATTERN_DISTRIBUTION_FILE = OUTPUT_DIR / "capital_allocation_distribution.csv"


# ============================================================
# HELPERS
# ============================================================

def normalize_company_id(value: Any) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def extract_year(value: Any) -> float:
    if pd.isna(value):
        return np.nan

    text = str(value).strip()

    try:
        numeric = float(text)

        if 1900 <= numeric <= 2100:
            return numeric
    except ValueError:
        pass

    import re

    match = re.search(r"(19|20)\d{2}", text)

    if match:
        return float(match.group())

    match = re.search(r"(?<!\d)(\d{2})(?!\d)", text)

    if match:
        year = int(match.group(1))

        if year <= 50:
            return float(2000 + year)

        return float(1900 + year)

    return np.nan


def detect_column(
    dataframe: pd.DataFrame,
    candidates: list[str],
    purpose: str,
) -> str:
    for column in candidates:
        if column in dataframe.columns:
            return column

    raise ValueError(
        f"Could not find {purpose} column. "
        f"Checked: {', '.join(candidates)}. "
        f"Available columns: {', '.join(dataframe.columns)}"
    )


# ============================================================
# LOAD AND PREPARE DATA
# ============================================================

def load_capital_allocation() -> tuple[pd.DataFrame, str]:
    if not CAPITAL_ALLOCATION_FILE.exists():
        raise FileNotFoundError(
            f"File not found: {CAPITAL_ALLOCATION_FILE}"
        )

    dataframe = pd.read_csv(CAPITAL_ALLOCATION_FILE)

    company_column = detect_column(
        dataframe,
        ["company_id", "ticker", "symbol"],
        "company identifier",
    )

    year_column = detect_column(
        dataframe,
        ["year", "financial_year", "fiscal_year"],
        "year",
    )

    pattern_column = detect_column(
        dataframe,
        [
            "capital_allocation_label",
            "capital_allocation_pattern",
            "allocation_pattern",
            "pattern_label",
            "pattern",
        ],
        "capital allocation pattern",
    )

    dataframe = dataframe.rename(
        columns={
            company_column: "company_id",
            year_column: "year",
            pattern_column: "capital_allocation_pattern",
        }
    )

    dataframe["company_id"] = (
        dataframe["company_id"].apply(normalize_company_id)
    )

    dataframe["_year_number"] = (
        dataframe["year"].apply(extract_year)
    )

    dataframe["capital_allocation_pattern"] = (
        dataframe["capital_allocation_pattern"]
        .fillna("Unavailable")
        .astype(str)
        .str.strip()
    )

    dataframe = dataframe[
        dataframe["company_id"] != ""
    ].copy()

    return dataframe, pattern_column


# ============================================================
# VALIDATION
# ============================================================

def validate_coverage(dataframe: pd.DataFrame) -> None:
    company_count = dataframe["company_id"].nunique()

    if company_count != 92:
        print(
            f"Warning: expected 92 companies, "
            f"but found {company_count}."
        )

    duplicate_count = dataframe.duplicated(
        subset=["company_id", "_year_number"]
    ).sum()

    if duplicate_count > 0:
        print(
            f"Warning: found {duplicate_count} duplicate "
            "company-year rows."
        )

    missing_years = dataframe["_year_number"].isna().sum()

    if missing_years > 0:
        print(
            f"Warning: {missing_years} rows have an "
            "unrecognized year value."
        )


# ============================================================
# LATEST-YEAR DISTRIBUTION
# ============================================================

def build_latest_distribution(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    valid_data = dataframe.dropna(
        subset=["_year_number"]
    ).copy()

    valid_data = valid_data.sort_values(
        ["company_id", "_year_number"]
    )

    latest_rows = valid_data.groupby(
        "company_id",
        as_index=False,
    ).tail(1)

    distribution = (
        latest_rows["capital_allocation_pattern"]
        .value_counts()
        .rename_axis("capital_allocation_pattern")
        .reset_index(name="company_count")
    )

    distribution["percentage"] = (
        distribution["company_count"]
        / len(latest_rows)
        * 100
    ).round(2)

    distribution = distribution.sort_values(
        ["company_count", "capital_allocation_pattern"],
        ascending=[False, True],
    ).reset_index(drop=True)

    return distribution


# ============================================================
# PATTERN CHANGES
# ============================================================

def build_pattern_changes(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    valid_data = dataframe.dropna(
        subset=["_year_number"]
    ).copy()

    valid_data = valid_data.sort_values(
        ["company_id", "_year_number"]
    )

    change_records = []

    for company_id, company_data in valid_data.groupby(
        "company_id"
    ):
        company_data = company_data.drop_duplicates(
            subset=["_year_number"],
            keep="last",
        )

        if len(company_data) < 2:
            continue

        previous_row = company_data.iloc[-2]
        latest_row = company_data.iloc[-1]

        previous_pattern = str(
            previous_row["capital_allocation_pattern"]
        ).strip()

        latest_pattern = str(
            latest_row["capital_allocation_pattern"]
        ).strip()

        if previous_pattern != latest_pattern:
            change_records.append(
                {
                    "company_id": company_id,
                    "previous_year": int(
                        previous_row["_year_number"]
                    ),
                    "latest_year": int(
                        latest_row["_year_number"]
                    ),
                    "previous_pattern": previous_pattern,
                    "latest_pattern": latest_pattern,
                    "change_description": (
                        f"Moved from {previous_pattern} "
                        f"to {latest_pattern}"
                    ),
                }
            )

    return pd.DataFrame(
        change_records,
        columns=[
            "company_id",
            "previous_year",
            "latest_year",
            "previous_pattern",
            "latest_pattern",
            "change_description",
        ],
    )


# ============================================================
# CASHFLOW EXCEL CHECK
# ============================================================

def verify_cashflow_intelligence() -> None:
    if not CASHFLOW_INTELLIGENCE_FILE.exists():
        raise FileNotFoundError(
            f"File not found: {CASHFLOW_INTELLIGENCE_FILE}"
        )

    dataframe = pd.read_excel(
        CASHFLOW_INTELLIGENCE_FILE
    )

    required_column = "capital_allocation_label"

    if required_column not in dataframe.columns:
        raise ValueError(
            f"{required_column} is missing from "
            "cashflow_intelligence.xlsx"
        )

    print(
        "Capital allocation column verified in "
        "cashflow_intelligence.xlsx"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 65)
    print("SPRINT 5 - DAY 32 - CAPITAL ALLOCATION REPORT")
    print("=" * 65)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe, original_pattern_column = (
        load_capital_allocation()
    )

    validate_coverage(dataframe)

    distribution = build_latest_distribution(
        dataframe
    )

    pattern_changes = build_pattern_changes(
        dataframe
    )

    distribution.to_csv(
        PATTERN_DISTRIBUTION_FILE,
        index=False,
    )

    pattern_changes.to_csv(
        PATTERN_CHANGES_FILE,
        index=False,
    )

    verify_cashflow_intelligence()

    company_count = dataframe[
        "company_id"
    ].nunique()

    total_rows = len(dataframe)

    year_count = dataframe[
        "_year_number"
    ].nunique()

    print(f"Companies found           : {company_count}")
    print(f"Company-year rows         : {total_rows}")
    print(f"Years available           : {year_count}")
    print(
        f"Pattern column used       : "
        f"{original_pattern_column}"
    )
    print(
        f"Latest-year patterns      : "
        f"{len(distribution)}"
    )
    print(
        f"Companies with changes    : "
        f"{len(pattern_changes)}"
    )

    print()
    print("Latest-year distribution:")
    print(distribution.to_string(index=False))

    print()
    print(f"Created: {PATTERN_DISTRIBUTION_FILE}")
    print(f"Created: {PATTERN_CHANGES_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()