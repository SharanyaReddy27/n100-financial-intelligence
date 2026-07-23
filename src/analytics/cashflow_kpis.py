from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ============================================================
# PATH CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"

CASHFLOW_FILE = DATA_DIR / "cashflow.csv"
PROFIT_LOSS_FILE = DATA_DIR / "profitandloss.csv"
BALANCE_SHEET_FILE = DATA_DIR / "balancesheet.csv"
FINANCIAL_RATIOS_FILE = DATA_DIR / "financial_ratios.csv"
SECTORS_FILE = DATA_DIR / "sectors.csv"

# Capital-allocation data may exist in either location.
CAPITAL_ALLOCATION_CANDIDATES = [
    OUTPUT_DIR / "capital_allocation.csv",
    DATA_DIR / "capital_allocation.csv",
]

OUTPUT_EXCEL_FILE = OUTPUT_DIR / "cashflow_intelligence.xlsx"
DISTRESS_ALERTS_FILE = OUTPUT_DIR / "distress_alerts.csv"


# ============================================================
# GENERAL HELPERS
# ============================================================

def normalize_company_id(value: Any) -> str:
    """Normalize company identifiers for safe merging."""
    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def extract_year_number(value: Any) -> float:
    """Extract a numeric year from common year formats."""
    if pd.isna(value):
        return np.nan

    text = str(value).strip()

    # Direct numeric year such as 2024 or 2024.0
    try:
        numeric = float(text)

        if 1900 <= numeric <= 2100:
            return numeric
    except ValueError:
        pass

    # Four-digit year inside text such as "Mar 2024"
    import re

    match = re.search(r"(19|20)\d{2}", text)

    if match:
        return float(match.group())

    # Two-digit year such as "Mar-24"
    match = re.search(r"(?<!\d)(\d{2})(?!\d)", text)

    if match:
        year = int(match.group(1))

        if year <= 50:
            return float(2000 + year)

        return float(1900 + year)

    return np.nan


def safe_divide(
    numerator: Any,
    denominator: Any,
) -> float:
    """Safely divide two values."""
    try:
        numerator = float(numerator)
        denominator = float(denominator)
    except (TypeError, ValueError):
        return np.nan

    if (
        not np.isfinite(numerator)
        or not np.isfinite(denominator)
        or denominator == 0
    ):
        return np.nan

    return numerator / denominator


def calculate_cagr(
    start_value: Any,
    end_value: Any,
    periods: int,
) -> float:
    """Calculate CAGR when start and end values are positive."""
    try:
        start_value = float(start_value)
        end_value = float(end_value)
    except (TypeError, ValueError):
        return np.nan

    if (
        not np.isfinite(start_value)
        or not np.isfinite(end_value)
        or start_value <= 0
        or end_value <= 0
        or periods <= 0
    ):
        return np.nan

    return (
        (end_value / start_value) ** (1 / periods) - 1
    ) * 100


def load_required_csv(path: Path) -> pd.DataFrame:
    """Load a required CSV file."""
    if not path.exists():
        raise FileNotFoundError(
            f"Required input file not found: {path}"
        )

    return pd.read_csv(path)


def load_optional_csv(path: Path) -> pd.DataFrame:
    """Load an optional CSV file."""
    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def prepare_dataframe(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
) -> pd.DataFrame:
    """Normalize IDs, years and numeric columns."""
    dataframe = dataframe.copy()

    if "company_id" not in dataframe.columns:
        raise ValueError(
            "Input dataframe does not contain company_id."
        )

    dataframe["company_id"] = (
        dataframe["company_id"]
        .apply(normalize_company_id)
    )

    if "year" in dataframe.columns:
        dataframe["_year_number"] = (
            dataframe["year"]
            .apply(extract_year_number)
        )
    else:
        dataframe["_year_number"] = np.nan

    for column in numeric_columns:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(
                dataframe[column],
                errors="coerce",
            )

    return dataframe


def latest_company_rows(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Return the latest available row for each company."""
    if dataframe.empty:
        return dataframe.copy()

    dataframe = dataframe.copy()

    dataframe["_original_order"] = np.arange(
        len(dataframe)
    )

    dataframe = dataframe.sort_values(
        [
            "company_id",
            "_year_number",
            "_original_order",
        ],
        na_position="first",
    )

    latest = dataframe.groupby(
        "company_id",
        as_index=False,
    ).tail(1)

    return latest.drop(
        columns=["_original_order"],
        errors="ignore",
    )


def get_previous_row(
    dataframe: pd.DataFrame,
    company_id: str,
) -> pd.Series | None:
    """Return the previous-year row for a company."""
    company_data = dataframe[
        dataframe["company_id"] == company_id
    ].copy()

    company_data = company_data.dropna(
        subset=["_year_number"]
    )

    company_data = company_data.sort_values(
        "_year_number"
    )

    if len(company_data) < 2:
        return None

    return company_data.iloc[-2]


def get_latest_row(
    dataframe: pd.DataFrame,
    company_id: str,
) -> pd.Series | None:
    """Return the latest row for one company."""
    company_data = dataframe[
        dataframe["company_id"] == company_id
    ].copy()

    if company_data.empty:
        return None

    company_data = company_data.sort_values(
        "_year_number",
        na_position="first",
    )

    return company_data.iloc[-1]


def get_value(
    row: pd.Series | None,
    column: str,
) -> float:
    """Read a numeric value from a row."""
    if row is None or column not in row.index:
        return np.nan

    value = row[column]

    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan

    return value if np.isfinite(value) else np.nan


def get_text(
    row: pd.Series | None,
    column: str,
) -> str:
    """Read a text value from a row."""
    if row is None or column not in row.index:
        return ""

    value = row[column]

    if pd.isna(value):
        return ""

    return str(value).strip()


# ============================================================
# CASH-FLOW CALCULATIONS
# ============================================================

def calculate_five_year_average_cfo_quality(
    cashflow: pd.DataFrame,
    profit_loss: pd.DataFrame,
    company_id: str,
) -> float:
    """
    Calculate average CFO/PAT over the latest five matched years.

    CFO Quality:
    - High Quality: > 1.0
    - Moderate: 0.5 to 1.0
    - Accrual Risk: < 0.5
    """
    company_cashflow = cashflow[
        cashflow["company_id"] == company_id
    ][
        [
            "company_id",
            "_year_number",
            "operating_activity",
        ]
    ].copy()

    company_profit = profit_loss[
        profit_loss["company_id"] == company_id
    ][
        [
            "company_id",
            "_year_number",
            "net_profit",
        ]
    ].copy()

    merged = company_cashflow.merge(
        company_profit,
        on=["company_id", "_year_number"],
        how="inner",
    )

    merged = merged.dropna(
        subset=["operating_activity", "net_profit"]
    )

    merged = merged[
        merged["net_profit"] != 0
    ].sort_values("_year_number").tail(5)

    if merged.empty:
        return np.nan

    merged["cfo_pat_ratio"] = (
        merged["operating_activity"]
        / merged["net_profit"]
    )

    finite_values = merged.loc[
        np.isfinite(merged["cfo_pat_ratio"]),
        "cfo_pat_ratio",
    ]

    if finite_values.empty:
        return np.nan

    return float(finite_values.mean())


def classify_cfo_quality(score: float) -> str:
    """Assign CFO quality label."""
    if not np.isfinite(score):
        return "Unavailable"

    if score > 1.0:
        return "High Quality"

    if score >= 0.5:
        return "Moderate"

    return "Accrual Risk"


def classify_capex_intensity(
    intensity_pct: float,
) -> str:
    """Assign CapEx intensity label."""
    if not np.isfinite(intensity_pct):
        return "Unavailable"

    if intensity_pct < 3:
        return "Asset Light"

    if intensity_pct <= 8:
        return "Moderate"

    return "Capital Intensive"


def calculate_fcf_cagr(
    financial_ratios: pd.DataFrame,
    company_id: str,
) -> float:
    """Calculate FCF CAGR using up to the latest five years."""
    company_data = financial_ratios[
        financial_ratios["company_id"] == company_id
    ][
        [
            "_year_number",
            "free_cash_flow_cr",
        ]
    ].copy()

    company_data = company_data.dropna(
        subset=["_year_number", "free_cash_flow_cr"]
    )

    company_data = company_data.sort_values(
        "_year_number"
    )

    if len(company_data) < 2:
        return np.nan

    latest_year = company_data[
        "_year_number"
    ].max()

    window = company_data[
        company_data["_year_number"]
        >= latest_year - 5
    ]

    if len(window) < 2:
        window = company_data.tail(2)

    first_row = window.iloc[0]
    last_row = window.iloc[-1]

    periods = int(
        last_row["_year_number"]
        - first_row["_year_number"]
    )

    return calculate_cagr(
        first_row["free_cash_flow_cr"],
        last_row["free_cash_flow_cr"],
        periods,
    )


def find_capital_allocation_file() -> Path | None:
    """Locate existing capital-allocation CSV."""
    for path in CAPITAL_ALLOCATION_CANDIDATES:
        if path.exists():
            return path

    return None


def load_capital_allocation() -> pd.DataFrame:
    """Load Sprint 2 capital-allocation output when available."""
    path = find_capital_allocation_file()

    if path is None:
        print(
            "Warning: capital_allocation.csv was not found. "
            "Capital-allocation labels will be derived from "
            "latest cash-flow signs."
        )
        return pd.DataFrame()

    dataframe = pd.read_csv(path)

    dataframe = prepare_dataframe(
        dataframe,
        numeric_columns=[],
    )

    print(f"Capital-allocation source: {path}")

    return dataframe


def extract_existing_capital_allocation_label(
    capital_allocation: pd.DataFrame,
    company_id: str,
) -> str:
    """Get the latest label from existing capital-allocation data."""
    if capital_allocation.empty:
        return ""

    row = get_latest_row(
        capital_allocation,
        company_id,
    )

    candidate_columns = [
        "capital_allocation_label",
        "pattern_label",
        "allocation_pattern",
        "capital_allocation_pattern",
        "pattern",
    ]

    for column in candidate_columns:
        value = get_text(row, column)

        if value:
            return value

    return ""


def derive_capital_allocation_label(
    cfo: float,
    cfi: float,
    cff: float,
    distress_flag: bool,
    deleveraging_flag: bool,
) -> str:
    """
    Derive a fallback capital-allocation label from cash-flow signs.

    Existing Sprint 2 labels take priority when available.
    """
    if distress_flag:
        return "Distress Signal"

    if deleveraging_flag:
        return "Deleveraging"

    if not all(
        np.isfinite(value)
        for value in [cfo, cfi, cff]
    ):
        return "Unavailable"

    if cfo > 0 and cfi < 0 and cff <= 0:
        return "Reinvestor"

    if cfo > 0 and cfi >= 0 and cff < 0:
        return "Liquidating Assets"

    if cfo > 0 and cfi < 0 and cff > 0:
        return "Expansion Financing"

    if cfo > 0 and cfi >= 0 and cff >= 0:
        return "Cash Accumulator"

    if cfo < 0 and cfi < 0 and cff > 0:
        return "Externally Funded Growth"

    if cfo < 0 and cfi >= 0 and cff > 0:
        return "Asset Sale Financing"

    if cfo < 0 and cff <= 0:
        return "Cash Burn"

    return "Mixed"


# ============================================================
# DATA LOADING
# ============================================================

def load_data() -> dict[str, pd.DataFrame]:
    """Load and prepare all Day 31 data sources."""
    cashflow = prepare_dataframe(
        load_required_csv(CASHFLOW_FILE),
        numeric_columns=[
            "operating_activity",
            "investing_activity",
            "financing_activity",
            "net_cash_flow",
        ],
    )

    profit_loss = prepare_dataframe(
        load_required_csv(PROFIT_LOSS_FILE),
        numeric_columns=[
            "sales",
            "net_profit",
        ],
    )

    balance_sheet = prepare_dataframe(
        load_required_csv(BALANCE_SHEET_FILE),
        numeric_columns=[
            "borrowings",
        ],
    )

    financial_ratios = prepare_dataframe(
        load_required_csv(FINANCIAL_RATIOS_FILE),
        numeric_columns=[
            "free_cash_flow_cr",
            "capex_cr",
            "cash_from_operations_cr",
        ],
    )

    sectors = prepare_dataframe(
        load_required_csv(SECTORS_FILE),
        numeric_columns=[],
    )

    capital_allocation = load_capital_allocation()

    return {
        "cashflow": cashflow,
        "profit_loss": profit_loss,
        "balance_sheet": balance_sheet,
        "financial_ratios": financial_ratios,
        "sectors": sectors,
        "capital_allocation": capital_allocation,
    }


# ============================================================
# COMPANY ANALYSIS
# ============================================================

def analyse_company(
    company_id: str,
    data: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Generate cash-flow intelligence for one company."""
    cashflow = data["cashflow"]
    profit_loss = data["profit_loss"]
    balance_sheet = data["balance_sheet"]
    financial_ratios = data["financial_ratios"]
    sectors = data["sectors"]
    capital_allocation = data["capital_allocation"]

    latest_cashflow = get_latest_row(
        cashflow,
        company_id,
    )

    latest_profit = get_latest_row(
        profit_loss,
        company_id,
    )

    latest_balance = get_latest_row(
        balance_sheet,
        company_id,
    )

    previous_balance = get_previous_row(
        balance_sheet,
        company_id,
    )

    latest_ratios = get_latest_row(
        financial_ratios,
        company_id,
    )

    latest_sector = get_latest_row(
        sectors,
        company_id,
    )

    latest_year = get_value(
        latest_cashflow,
        "_year_number",
    )

    cfo = get_value(
        latest_cashflow,
        "operating_activity",
    )

    cfi = get_value(
        latest_cashflow,
        "investing_activity",
    )

    cff = get_value(
        latest_cashflow,
        "financing_activity",
    )

    net_profit = get_value(
        latest_profit,
        "net_profit",
    )

    sales = get_value(
        latest_profit,
        "sales",
    )

    latest_borrowings = get_value(
        latest_balance,
        "borrowings",
    )

    previous_borrowings = get_value(
        previous_balance,
        "borrowings",
    )

    latest_fcf = get_value(
        latest_ratios,
        "free_cash_flow_cr",
    )

    if not np.isfinite(latest_fcf):
        capex = get_value(
            latest_ratios,
            "capex_cr",
        )

        if np.isfinite(cfo) and np.isfinite(capex):
            latest_fcf = cfo - abs(capex)

    cfo_quality_score = (
        calculate_five_year_average_cfo_quality(
            cashflow=cashflow,
            profit_loss=profit_loss,
            company_id=company_id,
        )
    )

    cfo_quality_label = classify_cfo_quality(
        cfo_quality_score
    )

    # Sprint definition:
    # abs(investing_activity) / sales * 100
    capex_intensity_pct = (
        safe_divide(abs(cfi), abs(sales)) * 100
        if np.isfinite(cfi) and np.isfinite(sales)
        else np.nan
    )

    capex_label = classify_capex_intensity(
        capex_intensity_pct
    )

    fcf_cagr_5yr = calculate_fcf_cagr(
        financial_ratios=financial_ratios,
        company_id=company_id,
    )

    # FCF conversion = FCF / PAT × 100
    fcf_conversion_pct = (
        safe_divide(latest_fcf, net_profit) * 100
        if np.isfinite(latest_fcf)
        and np.isfinite(net_profit)
        else np.nan
    )

    distress_flag = bool(
        np.isfinite(cfo)
        and np.isfinite(cff)
        and cfo < 0
        and cff > 0
    )

    borrowings_declining = bool(
        np.isfinite(latest_borrowings)
        and np.isfinite(previous_borrowings)
        and latest_borrowings < previous_borrowings
    )

    deleveraging_flag = bool(
        np.isfinite(cff)
        and cff < 0
        and borrowings_declining
    )

    existing_label = (
        extract_existing_capital_allocation_label(
            capital_allocation=capital_allocation,
            company_id=company_id,
        )
    )

    if existing_label:
        capital_allocation_label = existing_label
    else:
        capital_allocation_label = (
            derive_capital_allocation_label(
                cfo=cfo,
                cfi=cfi,
                cff=cff,
                distress_flag=distress_flag,
                deleveraging_flag=deleveraging_flag,
            )
        )

    sector = get_text(
        latest_sector,
        "broad_sector",
    )

    result = {
        "company_id": company_id,
        "sector": sector,
        "cfo_quality_score": (
            round(cfo_quality_score, 4)
            if np.isfinite(cfo_quality_score)
            else np.nan
        ),
        "cfo_quality_label": cfo_quality_label,
        "capex_intensity_pct": (
            round(capex_intensity_pct, 2)
            if np.isfinite(capex_intensity_pct)
            else np.nan
        ),
        "capex_label": capex_label,
        "fcf_cagr_5yr": (
            round(fcf_cagr_5yr, 2)
            if np.isfinite(fcf_cagr_5yr)
            else np.nan
        ),
        "fcf_conversion_pct": (
            round(fcf_conversion_pct, 2)
            if np.isfinite(fcf_conversion_pct)
            else np.nan
        ),
        "distress_flag": distress_flag,
        "deleveraging_flag": deleveraging_flag,
        "capital_allocation_label": (
            capital_allocation_label
        ),
    }

    distress_record = None

    if distress_flag:
        distress_record = {
            "company_id": company_id,
            "sector": sector,
            "year": (
                int(latest_year)
                if np.isfinite(latest_year)
                else ""
            ),
            "cfo_value": cfo,
            "cff_value": cff,
            "latest_net_profit": net_profit,
        }

    return result, distress_record


# ============================================================
# VALIDATION
# ============================================================

def validate_output(
    output_dataframe: pd.DataFrame,
    expected_company_count: int,
) -> None:
    """Validate required Day 31 output."""
    required_columns = [
        "company_id",
        "sector",
        "cfo_quality_score",
        "cfo_quality_label",
        "capex_intensity_pct",
        "capex_label",
        "fcf_cagr_5yr",
        "fcf_conversion_pct",
        "distress_flag",
        "deleveraging_flag",
        "capital_allocation_label",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in output_dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing output columns: "
            + ", ".join(missing_columns)
        )

    if len(output_dataframe) != expected_company_count:
        raise ValueError(
            f"Expected {expected_company_count} companies, "
            f"but generated {len(output_dataframe)}."
        )

    duplicate_count = output_dataframe[
        "company_id"
    ].duplicated().sum()

    if duplicate_count > 0:
        raise ValueError(
            f"Found {duplicate_count} duplicate company rows."
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Run Sprint 5 Day 31 Cash Flow Intelligence."""
    print("=" * 65)
    print("SPRINT 5 - DAY 31 - CASH FLOW INTELLIGENCE")
    print("=" * 65)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = load_data()

    company_ids = sorted(
        company_id
        for company_id in data[
            "sectors"
        ]["company_id"].dropna().unique()
        if company_id
    )

    results: list[dict[str, Any]] = []
    distress_records: list[dict[str, Any]] = []

    for company_id in company_ids:
        result, distress_record = analyse_company(
            company_id=company_id,
            data=data,
        )

        results.append(result)

        if distress_record is not None:
            distress_records.append(
                distress_record
            )

    output_dataframe = pd.DataFrame(results)

    distress_dataframe = pd.DataFrame(
        distress_records,
        columns=[
            "company_id",
            "sector",
            "year",
            "cfo_value",
            "cff_value",
            "latest_net_profit",
        ],
    )

    output_dataframe = output_dataframe.sort_values(
        "company_id"
    ).reset_index(drop=True)

    distress_dataframe = (
        distress_dataframe.sort_values(
            "company_id"
        ).reset_index(drop=True)
        if not distress_dataframe.empty
        else distress_dataframe
    )

    validate_output(
        output_dataframe=output_dataframe,
        expected_company_count=len(company_ids),
    )

    output_dataframe.to_excel(
        OUTPUT_EXCEL_FILE,
        index=False,
        engine="openpyxl",
    )

    distress_dataframe.to_csv(
        DISTRESS_ALERTS_FILE,
        index=False,
    )

    print(f"Companies available       : {len(company_ids)}")
    print(f"Companies processed       : {len(output_dataframe)}")

    print(
        "High Quality CFO         : "
        f"{int((output_dataframe['cfo_quality_label'] == 'High Quality').sum())}"
    )

    print(
        "Moderate CFO             : "
        f"{int((output_dataframe['cfo_quality_label'] == 'Moderate').sum())}"
    )

    print(
        "Accrual Risk             : "
        f"{int((output_dataframe['cfo_quality_label'] == 'Accrual Risk').sum())}"
    )

    print(
        "Distress alerts          : "
        f"{int(output_dataframe['distress_flag'].sum())}"
    )

    print(
        "Deleveraging companies   : "
        f"{int(output_dataframe['deleveraging_flag'].sum())}"
    )

    print()
    print(f"Created: {OUTPUT_EXCEL_FILE}")
    print(f"Created: {DISTRESS_ALERTS_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()