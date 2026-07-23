from __future__ import annotations

import json
import re
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

PROFIT_LOSS_FILE = DATA_DIR / "profitandloss.csv"
BALANCE_SHEET_FILE = DATA_DIR / "balancesheet.csv"
FINANCIAL_RATIOS_FILE = DATA_DIR / "financial_ratios.csv"
MARKET_CAP_FILE = DATA_DIR / "market_cap.csv"
SECTORS_FILE = DATA_DIR / "sectors.csv"

CAGR_FILE = OUTPUT_DIR / "day10_cagr_metrics.csv"
CASHFLOW_KPI_FILE = OUTPUT_DIR / "day11_cashflow_kpis.csv"

OUTPUT_FILE = OUTPUT_DIR / "pros_cons_generated.csv"
RULE_AUDIT_FILE = OUTPUT_DIR / "pros_cons_rule_audit.csv"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_numeric(value: Any) -> float:
    """Convert a value to float. Return NaN when conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def is_valid_number(value: Any) -> bool:
    """Check whether value is a valid finite number."""
    numeric_value = safe_numeric(value)
    return bool(np.isfinite(numeric_value))


def normalize_company_id(value: Any) -> str:
    """Normalize company identifiers."""
    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def extract_year_number(value: Any) -> float:
    """
    Extract a four-digit year from formats such as:
    Mar 2024
    Mar-24
    Dec 2012
    2023
    """
    if pd.isna(value):
        return np.nan

    text = str(value).strip()

    four_digit_match = re.search(r"(19|20)\d{2}", text)
    if four_digit_match:
        return float(four_digit_match.group())

    two_digit_match = re.search(r"(?<!\d)(\d{2})(?!\d)", text)
    if two_digit_match:
        year = int(two_digit_match.group(1))

        if year <= 50:
            return float(2000 + year)

        return float(1900 + year)

    return np.nan


def prepare_dataframe(
    dataframe: pd.DataFrame,
    numeric_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Clean company IDs and convert selected columns to numeric."""
    dataframe = dataframe.copy()

    if "company_id" in dataframe.columns:
        dataframe["company_id"] = (
            dataframe["company_id"]
            .apply(normalize_company_id)
        )

    if "year" in dataframe.columns:
        dataframe["_year_number"] = dataframe["year"].apply(extract_year_number)

    for column in numeric_columns or []:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(
                dataframe[column],
                errors="coerce",
            )

    return dataframe


def latest_company_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Select the latest available row for each company."""
    if dataframe.empty:
        return dataframe.copy()

    dataframe = dataframe.copy()

    if "_year_number" not in dataframe.columns:
        dataframe["_year_number"] = np.nan

    dataframe["_original_order"] = np.arange(len(dataframe))

    dataframe = dataframe.sort_values(
        by=["company_id", "_year_number", "_original_order"],
        na_position="first",
    )

    latest = dataframe.groupby(
        "company_id",
        as_index=False,
    ).tail(1)

    return latest.drop(columns=["_original_order"], errors="ignore")


def latest_n_company_rows(
    dataframe: pd.DataFrame,
    company_id: str,
    count: int,
) -> pd.DataFrame:
    """Return the latest N historical rows of a company."""
    company_data = dataframe[
        dataframe["company_id"] == company_id
    ].copy()

    company_data = company_data.dropna(subset=["_year_number"])

    return company_data.sort_values("_year_number").tail(count)


def calculate_cagr(
    start_value: Any,
    end_value: Any,
    periods: int,
) -> float:
    """Calculate CAGR when inputs are valid and positive."""
    start_value = safe_numeric(start_value)
    end_value = safe_numeric(end_value)

    if (
        not np.isfinite(start_value)
        or not np.isfinite(end_value)
        or start_value <= 0
        or end_value <= 0
        or periods <= 0
    ):
        return np.nan

    return ((end_value / start_value) ** (1 / periods) - 1) * 100


def calculate_historical_cagr(
    dataframe: pd.DataFrame,
    company_id: str,
    value_column: str,
    maximum_years: int = 5,
) -> float:
    """Calculate CAGR using up to the latest five years of history."""
    if value_column not in dataframe.columns:
        return np.nan

    company_data = dataframe[
        dataframe["company_id"] == company_id
    ][["_year_number", value_column]].copy()

    company_data = company_data.dropna(
        subset=["_year_number", value_column],
    )

    company_data = company_data.sort_values("_year_number")

    if len(company_data) < 2:
        return np.nan

    latest_year = company_data["_year_number"].max()
    minimum_year = latest_year - maximum_years

    window = company_data[
        company_data["_year_number"] >= minimum_year
    ]

    if len(window) < 2:
        window = company_data.tail(2)

    first_row = window.iloc[0]
    last_row = window.iloc[-1]

    periods = int(
        last_row["_year_number"] - first_row["_year_number"]
    )

    return calculate_cagr(
        first_row[value_column],
        last_row[value_column],
        periods,
    )


def trend_direction(
    dataframe: pd.DataFrame,
    company_id: str,
    value_column: str,
    periods: int = 3,
    tolerance_pct: float = 2.0,
) -> str:
    """
    Classify a historical trend as increasing, decreasing,
    stable or unavailable.
    """
    if value_column not in dataframe.columns:
        return "unavailable"

    company_data = latest_n_company_rows(
        dataframe=dataframe,
        company_id=company_id,
        count=periods,
    )

    company_data = company_data.dropna(subset=[value_column])

    if len(company_data) < periods:
        return "unavailable"

    values = company_data[value_column].astype(float).tolist()

    increasing = all(
        current >= previous
        for previous, current in zip(values, values[1:])
    )

    decreasing = all(
        current <= previous
        for previous, current in zip(values, values[1:])
    )

    first_value = values[0]
    last_value = values[-1]

    if first_value == 0:
        change_pct = np.nan
    else:
        change_pct = ((last_value - first_value) / abs(first_value)) * 100

    if is_valid_number(change_pct) and abs(change_pct) <= tolerance_pct:
        return "stable"

    if increasing and last_value > first_value:
        return "increasing"

    if decreasing and last_value < first_value:
        return "decreasing"

    return "mixed"


def positive_consecutive_years(
    dataframe: pd.DataFrame,
    company_id: str,
    value_column: str,
    periods: int,
) -> bool:
    """Check whether the latest N values are all positive."""
    if value_column not in dataframe.columns:
        return False

    company_data = latest_n_company_rows(
        dataframe=dataframe,
        company_id=company_id,
        count=periods,
    )

    company_data = company_data.dropna(subset=[value_column])

    if len(company_data) < periods:
        return False

    return bool((company_data[value_column] > 0).all())


def negative_consecutive_years(
    dataframe: pd.DataFrame,
    company_id: str,
    value_column: str,
    periods: int,
) -> bool:
    """Check whether the latest N values are all negative."""
    if value_column not in dataframe.columns:
        return False

    company_data = latest_n_company_rows(
        dataframe=dataframe,
        company_id=company_id,
        count=periods,
    )

    company_data = company_data.dropna(subset=[value_column])

    if len(company_data) < periods:
        return False

    return bool((company_data[value_column] < 0).all())


def get_value(
    dataframe: pd.DataFrame,
    company_id: str,
    column: str,
) -> float:
    """Get a value from a company-level latest-row dataframe."""
    if dataframe.empty or column not in dataframe.columns:
        return np.nan

    row = dataframe[dataframe["company_id"] == company_id]

    if row.empty:
        return np.nan

    return safe_numeric(row.iloc[0][column])


def get_text(
    dataframe: pd.DataFrame,
    company_id: str,
    column: str,
) -> str:
    """Get a text value from a company-level dataframe."""
    if dataframe.empty or column not in dataframe.columns:
        return ""

    row = dataframe[dataframe["company_id"] == company_id]

    if row.empty or pd.isna(row.iloc[0][column]):
        return ""

    return str(row.iloc[0][column]).strip()


def find_first_available_value(
    dataframe: pd.DataFrame,
    company_id: str,
    candidate_columns: list[str],
) -> float:
    """Get the first valid value from a list of candidate columns."""
    for column in candidate_columns:
        value = get_value(dataframe, company_id, column)

        if is_valid_number(value):
            return value

    return np.nan


def is_financial_company(
    broad_sector: str,
    sub_sector: str,
) -> bool:
    """
    Identify companies for which conventional leverage rules
    may not be directly comparable.
    """
    combined = f"{broad_sector} {sub_sector}".lower()

    keywords = [
        "bank",
        "financial",
        "insurance",
        "nbfc",
        "lending",
        "finance",
    ]

    return any(keyword in combined for keyword in keywords)


def format_number(value: float, decimals: int = 1) -> str:
    """Format a numeric value safely."""
    if not is_valid_number(value):
        return "N/A"

    return f"{value:.{decimals}f}"


# ============================================================
# DATA LOADING
# ============================================================

def load_required_csv(path: Path) -> pd.DataFrame:
    """Load a required CSV file with clear error reporting."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    return pd.read_csv(path)


def load_optional_csv(path: Path) -> pd.DataFrame:
    """Load optional CSV or return an empty dataframe."""
    if not path.exists():
        print(f"Warning: optional file not found: {path}")
        return pd.DataFrame()

    return pd.read_csv(path)


def load_data() -> dict[str, pd.DataFrame]:
    """Load and prepare all Day 30 source files."""
    profit_loss = load_required_csv(PROFIT_LOSS_FILE)
    balance_sheet = load_required_csv(BALANCE_SHEET_FILE)
    financial_ratios = load_required_csv(FINANCIAL_RATIOS_FILE)
    market_cap = load_required_csv(MARKET_CAP_FILE)
    sectors = load_required_csv(SECTORS_FILE)

    cagr_metrics = load_optional_csv(CAGR_FILE)
    cashflow_kpis = load_optional_csv(CASHFLOW_KPI_FILE)

    profit_loss = prepare_dataframe(
        profit_loss,
        numeric_columns=[
            "sales",
            "operating_profit",
            "opm_percentage",
            "interest",
            "net_profit",
            "eps",
            "dividend_payout",
        ],
    )

    balance_sheet = prepare_dataframe(
        balance_sheet,
        numeric_columns=[
            "borrowings",
            "total_liabilities",
            "total_assets",
            "reserves",
        ],
    )

    financial_ratios = prepare_dataframe(
        financial_ratios,
        numeric_columns=[
            "net_profit_margin_pct",
            "operating_profit_margin_pct",
            "return_on_equity_pct",
            "debt_to_equity",
            "interest_coverage",
            "free_cash_flow_cr",
            "capex_cr",
            "earnings_per_share",
            "dividend_payout_ratio_pct",
            "total_debt_cr",
            "cash_from_operations_cr",
        ],
    )

    market_cap = prepare_dataframe(
        market_cap,
        numeric_columns=[
            "market_cap_crore",
            "enterprise_value_crore",
            "pe_ratio",
            "pb_ratio",
            "ev_ebitda",
            "dividend_yield_pct",
        ],
    )

    sectors = prepare_dataframe(
        sectors,
        numeric_columns=["index_weight_pct"],
    )

    if not cagr_metrics.empty:
        cagr_metrics = prepare_dataframe(cagr_metrics)

        for column in cagr_metrics.columns:
            if column not in ["company_id", "year"]:
                converted = pd.to_numeric(
            	    cagr_metrics[column],
            	    errors="coerce",
                )

                if converted.notna().sum() > 0:
                    cagr_metrics[column] = converted

    if not cashflow_kpis.empty:
        cashflow_kpis = prepare_dataframe(
            cashflow_kpis,
            numeric_columns=[
                "free_cash_flow_cr",
                "cfo_quality_ratio",
                "capex_intensity_pct",
                "fcf_conversion_rate_pct",
            ],
        )

    return {
        "profit_loss": profit_loss,
        "balance_sheet": balance_sheet,
        "financial_ratios": financial_ratios,
        "market_cap": market_cap,
        "sectors": sectors,
        "cagr_metrics": cagr_metrics,
        "cashflow_kpis": cashflow_kpis,
    }


# ============================================================
# RULE ENGINE
# ============================================================

def generate_company_analysis(
    company_id: str,
    data: dict[str, pd.DataFrame],
    latest_data: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply pros and cons rules for one company."""

    profit_loss = data["profit_loss"]
    balance_sheet = data["balance_sheet"]
    financial_ratios = data["financial_ratios"]
    cashflow_kpis = data["cashflow_kpis"]

    latest_ratios = latest_data["financial_ratios"]
    latest_market = latest_data["market_cap"]
    latest_cagr = latest_data["cagr_metrics"]
    latest_cashflow = latest_data["cashflow_kpis"]
    sectors = latest_data["sectors"]

    broad_sector = get_text(sectors, company_id, "broad_sector")
    sub_sector = get_text(sectors, company_id, "sub_sector")

    financial_company = is_financial_company(
        broad_sector=broad_sector,
        sub_sector=sub_sector,
    )

    revenue_cagr = find_first_available_value(
        latest_cagr,
        company_id,
        [
            "revenue_cagr_5yr",
            "sales_cagr_5yr",
        ],
    )

    if not is_valid_number(revenue_cagr):
        revenue_cagr = calculate_historical_cagr(
            dataframe=profit_loss,
            company_id=company_id,
            value_column="sales",
            maximum_years=5,
        )

    pat_cagr = find_first_available_value(
        latest_cagr,
        company_id,
        [
            "pat_cagr_5yr",
            "profit_cagr_5yr",
            "net_profit_cagr_5yr",
        ],
    )

    if not is_valid_number(pat_cagr):
        pat_cagr = calculate_historical_cagr(
            dataframe=profit_loss,
            company_id=company_id,
            value_column="net_profit",
            maximum_years=5,
        )

    eps_cagr = find_first_available_value(
        latest_cagr,
        company_id,
        ["eps_cagr_5yr"],
    )

    if not is_valid_number(eps_cagr):
        eps_cagr = calculate_historical_cagr(
            dataframe=profit_loss,
            company_id=company_id,
            value_column="eps",
            maximum_years=5,
        )

    roe = get_value(
        latest_ratios,
        company_id,
        "return_on_equity_pct",
    )

    opm = get_value(
        latest_ratios,
        company_id,
        "operating_profit_margin_pct",
    )

    debt_to_equity = get_value(
        latest_ratios,
        company_id,
        "debt_to_equity",
    )

    interest_coverage = get_value(
        latest_ratios,
        company_id,
        "interest_coverage",
    )

    latest_fcf = find_first_available_value(
        latest_cashflow,
        company_id,
        ["free_cash_flow_cr"],
    )

    if not is_valid_number(latest_fcf):
        latest_fcf = get_value(
            latest_ratios,
            company_id,
            "free_cash_flow_cr",
        )

    dividend_payout = get_value(
        latest_ratios,
        company_id,
        "dividend_payout_ratio_pct",
    )

    dividend_yield = get_value(
        latest_market,
        company_id,
        "dividend_yield_pct",
    )

    pe_ratio = get_value(
        latest_market,
        company_id,
        "pe_ratio",
    )

    pb_ratio = get_value(
        latest_market,
        company_id,
        "pb_ratio",
    )

    cfo_quality_label = get_text(
        latest_cashflow,
        company_id,
        "cfo_quality_label",
    )

    pattern_label = get_text(
        latest_cashflow,
        company_id,
        "pattern_label",
    )

    assets_trend = trend_direction(
        dataframe=balance_sheet,
        company_id=company_id,
        value_column="total_assets",
        periods=3,
    )

    borrowings_trend = trend_direction(
        dataframe=balance_sheet,
        company_id=company_id,
        value_column="borrowings",
        periods=3,
    )

    sales_trend = trend_direction(
        dataframe=profit_loss,
        company_id=company_id,
        value_column="sales",
        periods=3,
    )

    opm_trend = trend_direction(
        dataframe=profit_loss,
        company_id=company_id,
        value_column="opm_percentage",
        periods=3,
    )

    eps_trend = trend_direction(
        dataframe=profit_loss,
        company_id=company_id,
        value_column="eps",
        periods=3,
    )

    roe_trend = trend_direction(
        dataframe=financial_ratios,
        company_id=company_id,
        value_column="return_on_equity_pct",
        periods=3,
    )

    five_year_positive_fcf = positive_consecutive_years(
        dataframe=cashflow_kpis,
        company_id=company_id,
        value_column="free_cash_flow_cr",
        periods=5,
    )

    three_year_negative_fcf = negative_consecutive_years(
        dataframe=cashflow_kpis,
        company_id=company_id,
        value_column="free_cash_flow_cr",
        periods=3,
    )

    pros: list[str] = []
    cons: list[str] = []
    audit_records: list[dict[str, Any]] = []

    evaluated_rules = 0
    triggered_rules = 0
    evidence_points = 0

    def add_rule(
        rule_id: str,
        rule_type: str,
        condition: bool,
        message: str,
        metric_name: str,
        metric_value: Any,
        weight: int = 1,
        evaluable: bool = True,
    ) -> None:
        nonlocal evaluated_rules
        nonlocal triggered_rules
        nonlocal evidence_points

        if evaluable:
            evaluated_rules += 1

        triggered = bool(condition and evaluable)

        if triggered:
            triggered_rules += 1
            evidence_points += weight

            if rule_type == "pro":
                pros.append(message)
            else:
                cons.append(message)

        audit_records.append(
            {
                "company_id": company_id,
                "rule_id": rule_id,
                "rule_type": rule_type,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "triggered": triggered,
                "evaluable": evaluable,
                "message": message if triggered else "",
            }
        )

    # --------------------------------------------------------
    # PRO RULES
    # --------------------------------------------------------

    add_rule(
        rule_id="PRO_01",
        rule_type="pro",
        condition=revenue_cagr > 15,
        message=(
            f"Strong revenue growth with a five-year CAGR of "
            f"{format_number(revenue_cagr)}%."
        ),
        metric_name="revenue_cagr_5yr",
        metric_value=revenue_cagr,
        weight=2,
        evaluable=is_valid_number(revenue_cagr),
    )

    add_rule(
        rule_id="PRO_02",
        rule_type="pro",
        condition=pat_cagr > 15,
        message=(
            f"Strong profit growth with a five-year PAT CAGR of "
            f"{format_number(pat_cagr)}%."
        ),
        metric_name="pat_cagr_5yr",
        metric_value=pat_cagr,
        weight=2,
        evaluable=is_valid_number(pat_cagr),
    )

    add_rule(
        rule_id="PRO_03",
        rule_type="pro",
        condition=roe > 20,
        message=(
            f"High return on equity of {format_number(roe)}%, "
            f"indicating efficient use of shareholder capital."
        ),
        metric_name="return_on_equity_pct",
        metric_value=roe,
        weight=2,
        evaluable=is_valid_number(roe),
    )

    add_rule(
        rule_id="PRO_04",
        rule_type="pro",
        condition=opm > 20,
        message=(
            f"Healthy operating margin of {format_number(opm)}%."
        ),
        metric_name="operating_profit_margin_pct",
        metric_value=opm,
        weight=1,
        evaluable=is_valid_number(opm),
    )

    add_rule(
        rule_id="PRO_05",
        rule_type="pro",
        condition=debt_to_equity < 0.5,
        message=(
            f"Conservative leverage with debt-to-equity of "
            f"{format_number(debt_to_equity, 2)}."
        ),
        metric_name="debt_to_equity",
        metric_value=debt_to_equity,
        weight=2,
        evaluable=(
            is_valid_number(debt_to_equity)
            and not financial_company
        ),
    )

    add_rule(
        rule_id="PRO_06",
        rule_type="pro",
        condition=interest_coverage > 5,
        message=(
            f"Comfortable interest coverage of "
            f"{format_number(interest_coverage, 2)} times."
        ),
        metric_name="interest_coverage",
        metric_value=interest_coverage,
        weight=2,
        evaluable=(
            is_valid_number(interest_coverage)
            and not financial_company
        ),
    )

    add_rule(
        rule_id="PRO_07",
        rule_type="pro",
        condition=five_year_positive_fcf,
        message="Generated positive free cash flow for five consecutive years.",
        metric_name="five_year_positive_fcf",
        metric_value=five_year_positive_fcf,
        weight=3,
        evaluable=(
            not cashflow_kpis[
                cashflow_kpis["company_id"] == company_id
            ].empty
        ),
    )

    add_rule(
        rule_id="PRO_08",
        rule_type="pro",
        condition=roe_trend == "increasing",
        message="Return on equity has improved across the latest three periods.",
        metric_name="roe_trend",
        metric_value=roe_trend,
        weight=2,
        evaluable=roe_trend != "unavailable",
    )

    add_rule(
        rule_id="PRO_09",
        rule_type="pro",
        condition=assets_trend == "increasing",
        message="Total assets have grown consistently across the latest three periods.",
        metric_name="total_assets_trend",
        metric_value=assets_trend,
        weight=1,
        evaluable=assets_trend != "unavailable",
    )

    add_rule(
        rule_id="PRO_10",
        rule_type="pro",
        condition=borrowings_trend == "decreasing",
        message="Borrowings have declined across the latest three periods.",
        metric_name="borrowings_trend",
        metric_value=borrowings_trend,
        weight=2,
        evaluable=(
            borrowings_trend != "unavailable"
            and not financial_company
        ),
    )

    add_rule(
        rule_id="PRO_11",
        rule_type="pro",
        condition=dividend_yield > 2,
        message=(
            f"Offers a dividend yield of "
            f"{format_number(dividend_yield)}%."
        ),
        metric_name="dividend_yield_pct",
        metric_value=dividend_yield,
        weight=1,
        evaluable=is_valid_number(dividend_yield),
    )

    add_rule(
        rule_id="PRO_12",
        rule_type="pro",
        condition=eps_cagr > 15,
        message=(
            f"Strong EPS growth with a five-year CAGR of "
            f"{format_number(eps_cagr)}%."
        ),
        metric_name="eps_cagr_5yr",
        metric_value=eps_cagr,
        weight=2,
        evaluable=is_valid_number(eps_cagr),
    )

    add_rule(
        rule_id="PRO_13",
        rule_type="pro",
        condition=cfo_quality_label.lower() in {
            "excellent",
            "strong",
            "high quality",
        },
        message=(
            f"Cash-flow quality is classified as "
            f"{cfo_quality_label}."
        ),
        metric_name="cfo_quality_label",
        metric_value=cfo_quality_label,
        weight=2,
        evaluable=bool(cfo_quality_label),
    )

    add_rule(
        rule_id="PRO_14",
        rule_type="pro",
        condition=pattern_label.lower() in {
            "reinvestor",
            "self-funded growth",
            "cash generator",
        },
        message=(
            f"Capital-allocation pattern is classified as "
            f"{pattern_label}."
        ),
        metric_name="pattern_label",
        metric_value=pattern_label,
        weight=1,
        evaluable=bool(pattern_label),
    )

    # --------------------------------------------------------
    # CON RULES
    # --------------------------------------------------------

    add_rule(
        rule_id="CON_01",
        rule_type="con",
        condition=revenue_cagr < 5,
        message=(
            f"Revenue growth is subdued, with a five-year CAGR of "
            f"{format_number(revenue_cagr)}%."
        ),
        metric_name="revenue_cagr_5yr",
        metric_value=revenue_cagr,
        weight=2,
        evaluable=is_valid_number(revenue_cagr),
    )

    add_rule(
        rule_id="CON_02",
        rule_type="con",
        condition=pat_cagr < 5,
        message=(
            f"Profit growth is weak, with a five-year PAT CAGR of "
            f"{format_number(pat_cagr)}%."
        ),
        metric_name="pat_cagr_5yr",
        metric_value=pat_cagr,
        weight=2,
        evaluable=is_valid_number(pat_cagr),
    )

    add_rule(
        rule_id="CON_03",
        rule_type="con",
        condition=roe < 10,
        message=(
            f"Low return on equity of {format_number(roe)}%."
        ),
        metric_name="return_on_equity_pct",
        metric_value=roe,
        weight=2,
        evaluable=is_valid_number(roe),
    )

    add_rule(
        rule_id="CON_04",
        rule_type="con",
        condition=opm < 10,
        message=(
            f"Operating margin is relatively low at "
            f"{format_number(opm)}%."
        ),
        metric_name="operating_profit_margin_pct",
        metric_value=opm,
        weight=1,
        evaluable=is_valid_number(opm),
    )

    add_rule(
        rule_id="CON_05",
        rule_type="con",
        condition=debt_to_equity > 2,
        message=(
            f"High leverage with debt-to-equity of "
            f"{format_number(debt_to_equity, 2)}."
        ),
        metric_name="debt_to_equity",
        metric_value=debt_to_equity,
        weight=3,
        evaluable=(
            is_valid_number(debt_to_equity)
            and not financial_company
        ),
    )

    add_rule(
        rule_id="CON_06",
        rule_type="con",
        condition=interest_coverage < 2,
        message=(
            f"Weak interest coverage of "
            f"{format_number(interest_coverage, 2)} times."
        ),
        metric_name="interest_coverage",
        metric_value=interest_coverage,
        weight=3,
        evaluable=(
            is_valid_number(interest_coverage)
            and not financial_company
        ),
    )

    add_rule(
        rule_id="CON_07",
        rule_type="con",
        condition=three_year_negative_fcf,
        message="Free cash flow has remained negative for three consecutive years.",
        metric_name="three_year_negative_fcf",
        metric_value=three_year_negative_fcf,
        weight=3,
        evaluable=(
            not cashflow_kpis[
                cashflow_kpis["company_id"] == company_id
            ].empty
        ),
    )

    add_rule(
        rule_id="CON_08",
        rule_type="con",
        condition=dividend_payout > 100,
        message=(
            f"Dividend payout of {format_number(dividend_payout)}% "
            f"exceeds reported earnings."
        ),
        metric_name="dividend_payout_ratio_pct",
        metric_value=dividend_payout,
        weight=2,
        evaluable=is_valid_number(dividend_payout),
    )

    add_rule(
        rule_id="CON_09",
        rule_type="con",
        condition=sales_trend == "decreasing",
        message="Sales have declined across the latest three periods.",
        metric_name="sales_trend",
        metric_value=sales_trend,
        weight=2,
        evaluable=sales_trend != "unavailable",
    )

    add_rule(
        rule_id="CON_10",
        rule_type="con",
        condition=opm_trend == "decreasing",
        message="Operating margins have declined across the latest three periods.",
        metric_name="opm_trend",
        metric_value=opm_trend,
        weight=2,
        evaluable=opm_trend != "unavailable",
    )

    add_rule(
        rule_id="CON_11",
        rule_type="con",
        condition=eps_trend == "decreasing",
        message="Earnings per share have declined across the latest three periods.",
        metric_name="eps_trend",
        metric_value=eps_trend,
        weight=2,
        evaluable=eps_trend != "unavailable",
    )

    add_rule(
        rule_id="CON_12",
        rule_type="con",
        condition=borrowings_trend == "increasing",
        message="Borrowings have increased across the latest three periods.",
        metric_name="borrowings_trend",
        metric_value=borrowings_trend,
        weight=2,
        evaluable=(
            borrowings_trend != "unavailable"
            and not financial_company
        ),
    )

    add_rule(
        rule_id="CON_13",
        rule_type="con",
        condition=cfo_quality_label.lower() in {
            "weak",
            "accrual risk",
            "poor",
        },
        message=(
            f"Cash-flow quality is classified as "
            f"{cfo_quality_label}."
        ),
        metric_name="cfo_quality_label",
        metric_value=cfo_quality_label,
        weight=2,
        evaluable=bool(cfo_quality_label),
    )

    add_rule(
        rule_id="CON_14",
        rule_type="con",
        condition=pattern_label.lower() in {
            "distress financing",
            "cash burner",
            "debt-funded",
        },
        message=(
            f"Capital-allocation pattern is classified as "
            f"{pattern_label}."
        ),
        metric_name="pattern_label",
        metric_value=pattern_label,
        weight=3,
        evaluable=bool(pattern_label),
    )

    if not pros:
        pros.append(
            "No major positive rule was triggered using the available financial data."
        )

    if not cons:
        cons.append(
            "No major negative rule was triggered using the available financial data."
        )

    total_rules = 28

    data_coverage_score = (
        evaluated_rules / total_rules * 100
        if total_rules
        else 0
    )

    evidence_score = min(evidence_points * 5, 100)

    confidence_score = round(
        (0.70 * data_coverage_score)
        + (0.30 * evidence_score),
        2,
    )

    result = {
        "company_id": company_id,
        "broad_sector": broad_sector,
        "sub_sector": sub_sector,
        "pros": json.dumps(pros, ensure_ascii=False),
        "cons": json.dumps(cons, ensure_ascii=False),
        "pro_count": len(
            [
                record
                for record in audit_records
                if record["rule_type"] == "pro"
                and record["triggered"]
            ]
        ),
        "con_count": len(
            [
                record
                for record in audit_records
                if record["rule_type"] == "con"
                and record["triggered"]
            ]
        ),
        "rules_evaluated": evaluated_rules,
        "rules_triggered": triggered_rules,
        "confidence_score": confidence_score,
        "latest_roe_pct": roe,
        "latest_opm_pct": opm,
        "debt_to_equity": debt_to_equity,
        "interest_coverage": interest_coverage,
        "revenue_cagr_5yr": revenue_cagr,
        "pat_cagr_5yr": pat_cagr,
        "eps_cagr_5yr": eps_cagr,
        "latest_fcf_cr": latest_fcf,
        "dividend_yield_pct": dividend_yield,
        "pe_ratio": pe_ratio,
        "pb_ratio": pb_ratio,
        "cfo_quality_label": cfo_quality_label,
        "capital_allocation_pattern": pattern_label,
    }

    return result, audit_records


# ============================================================
# MAIN EXECUTION
# ============================================================

def main() -> None:
    """Run the Day 30 pros and cons generator."""
    print("=" * 65)
    print("SPRINT 5 - DAY 30 - AUTOMATIC PROS/CONS GENERATOR")
    print("=" * 65)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = load_data()

    latest_data = {
        "financial_ratios": latest_company_rows(
            data["financial_ratios"]
        ),
        "market_cap": latest_company_rows(
            data["market_cap"]
        ),
        "sectors": latest_company_rows(
            data["sectors"]
        ),
        "cagr_metrics": (
            latest_company_rows(data["cagr_metrics"])
            if not data["cagr_metrics"].empty
            else pd.DataFrame()
        ),
        "cashflow_kpis": (
            latest_company_rows(data["cashflow_kpis"])
            if not data["cashflow_kpis"].empty
            else pd.DataFrame()
        ),
    }

    company_ids = sorted(
        company_id
        for company_id in data["sectors"]["company_id"].dropna().unique()
        if company_id
    )

    generated_results: list[dict[str, Any]] = []
    all_audit_records: list[dict[str, Any]] = []

    for company_id in company_ids:
        result, audit_records = generate_company_analysis(
            company_id=company_id,
            data=data,
            latest_data=latest_data,
        )

        generated_results.append(result)
        all_audit_records.extend(audit_records)

    output_dataframe = pd.DataFrame(generated_results)
    audit_dataframe = pd.DataFrame(all_audit_records)

    output_dataframe = output_dataframe.sort_values(
        "company_id"
    ).reset_index(drop=True)

    audit_dataframe = audit_dataframe.sort_values(
        ["company_id", "rule_id"]
    ).reset_index(drop=True)

    output_dataframe.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    audit_dataframe.to_csv(
        RULE_AUDIT_FILE,
        index=False,
    )

    print(f"Companies available       : {len(company_ids)}")
    print(f"Companies processed       : {len(output_dataframe)}")
    print(
        f"Companies with pros       : "
        f"{int((output_dataframe['pro_count'] > 0).sum())}"
    )
    print(
        f"Companies with cons       : "
        f"{int((output_dataframe['con_count'] > 0).sum())}"
    )
    print(
        f"Average confidence score  : "
        f"{output_dataframe['confidence_score'].mean():.2f}"
    )
    print(f"Rule audit rows           : {len(audit_dataframe)}")
    print()
    print(f"Created: {OUTPUT_FILE}")
    print(f"Created: {RULE_AUDIT_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()