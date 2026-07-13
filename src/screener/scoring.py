import numpy as np
import pandas as pd


def clean_company_id(df):
    df = df.copy()

    df["company_id"] = (
        df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return df


def extract_year_number(series):
    return pd.to_numeric(
        series.astype(str).str.extract(r"(\d{4})")[0],
        errors="coerce",
    )


def calculate_fcf_cagr_5yr(group):
    """
    Calculate latest 5-year Free Cash Flow CAGR.

    CAGR is calculated only when:
    - At least 6 annual records are available
    - Start and end FCF values are both positive
    """

    group = group.sort_values("year_num")

    if len(group) < 6:
        return np.nan

    start_value = group.iloc[-6]["free_cash_flow_cr"]
    end_value = group.iloc[-1]["free_cash_flow_cr"]

    if pd.isna(start_value) or pd.isna(end_value):
        return np.nan

    if start_value <= 0 or end_value <= 0:
        return np.nan

    return (
        ((end_value / start_value) ** (1 / 5)) - 1
    ) * 100


def load_scoring_inputs():
    profitability = pd.read_csv(
        "output/day08_profitability_ratios.csv"
    )

    cashflow = pd.read_csv(
        "output/day11_cashflow_kpis.csv"
    )

    profitability = clean_company_id(profitability)
    cashflow = clean_company_id(cashflow)

    # Remove TTM records
    profitability = profitability[
        profitability["year"].astype(str).str.upper() != "TTM"
    ].copy()

    cashflow = cashflow[
        cashflow["year"].astype(str).str.upper() != "TTM"
    ].copy()

    profitability["year_num"] = extract_year_number(
        profitability["year"]
    )

    cashflow["year_num"] = extract_year_number(
        cashflow["year"]
    )

    # Latest profitability values
    latest_profitability = (
        profitability
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    # Latest cash-flow values
    latest_cashflow = (
        cashflow
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    # Calculate 5-year FCF CAGR for each company
    fcf_cagr = (
        cashflow
        .dropna(subset=["year_num"])
        .groupby("company_id")
        .apply(calculate_fcf_cagr_5yr)
        .reset_index(name="fcf_cagr_5yr")
    )

    scoring_inputs = latest_profitability[
        [
            "company_id",
            "return_on_capital_employed_pct",
        ]
    ].merge(
        latest_cashflow[
            [
                "company_id",
                "cfo_quality_ratio",
            ]
        ],
        on="company_id",
        how="outer",
    )

    scoring_inputs = scoring_inputs.merge(
        fcf_cagr,
        on="company_id",
        how="outer",
    )

    return scoring_inputs


def add_scoring_inputs(df):
    df = df.copy()

    scoring_inputs = load_scoring_inputs()

    df = df.merge(
        scoring_inputs,
        on="company_id",
        how="left",
    )

    return df


def sector_percentile_score(
    group,
    column,
    higher_is_better=True,
):
    """
    Winsorise using sector P10/P90 and scale to 0–100.
    """

    values = pd.to_numeric(
        group[column],
        errors="coerce",
    )

    valid_values = values.dropna()

    result = pd.Series(
        0.0,
        index=group.index,
    )

    if valid_values.empty:
        return result

    p10 = valid_values.quantile(0.10)
    p90 = valid_values.quantile(0.90)

    if p90 == p10:
        result.loc[values.notna()] = 50.0
        return result

    capped = values.clip(
        lower=p10,
        upper=p90,
    )

    scaled = (
        (capped - p10)
        / (p90 - p10)
        * 100
    )

    if not higher_is_better:
        scaled = 100 - scaled

    result.loc[scaled.notna()] = scaled[
        scaled.notna()
    ]

    return result.clip(0, 100)


def add_composite_quality_score(df):
    df = df.copy()

    if "broad_sector" not in df.columns:
        raise KeyError(
            "broad_sector is required for sector-relative scoring."
        )

    metric_settings = {
        # Profitability: 35 points
        "return_on_equity_pct": {
            "weight": 15,
            "higher_is_better": True,
        },
        "return_on_capital_employed_pct": {
            "weight": 10,
            "higher_is_better": True,
        },
        "net_profit_margin_pct": {
            "weight": 10,
            "higher_is_better": True,
        },

        # Cash quality: 25 numeric points
        "fcf_cagr_5yr": {
            "weight": 15,
            "higher_is_better": True,
        },
        "cfo_quality_ratio": {
            "weight": 10,
            "higher_is_better": True,
        },

        # Growth: 20 points
        "revenue_cagr_5yr": {
            "weight": 10,
            "higher_is_better": True,
        },
        "pat_cagr_5yr": {
            "weight": 10,
            "higher_is_better": True,
        },

        # Leverage: 15 points
        "debt_to_equity": {
            "weight": 10,
            "higher_is_better": False,
        },
        "interest_coverage": {
            "weight": 5,
            "higher_is_better": True,
        },
    }

    total_score = pd.Series(
        0.0,
        index=df.index,
    )

    for column, settings in metric_settings.items():
        if column not in df.columns:
            df[column] = np.nan

        metric_score = (
            df.groupby(
                "broad_sector",
                group_keys=False,
            )
            .apply(
                lambda group: sector_percentile_score(
                    group,
                    column,
                    settings["higher_is_better"],
                )
            )
        )

        component_name = f"{column}_score"

        df[component_name] = metric_score.round(2)

        total_score += (
            metric_score
            * settings["weight"]
            / 100
        )

    # Positive FCF flag contributes 5 points
    df["fcf_positive_score"] = (
        df["free_cash_flow_cr"]
        .fillna(0)
        .gt(0)
        .astype(int)
        * 5
    )

    total_score += df["fcf_positive_score"]

    df["composite_quality_score"] = (
        total_score
        .clip(0, 100)
        .round(2)
    )

    return df