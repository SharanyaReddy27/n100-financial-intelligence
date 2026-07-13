import os
import sqlite3
import sys

import pandas as pd
import yaml

sys.path.append(os.path.abspath("."))
from src.screener.scoring import (
    add_scoring_inputs,
    add_composite_quality_score,
)

def load_config(config_path="config/screener_config.yaml"):
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not config:
        raise ValueError("Screener configuration is empty.")

    return config


def clean_company_id(df):
    df = df.copy()

    if "company_id" in df.columns:
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


def load_financial_data(db_path="db/nifty100.db"):
    conn = sqlite3.connect(db_path)

    ratios = pd.read_sql_query(
        "SELECT * FROM financial_ratios",
        conn,
    )

    sectors = pd.read_sql_query(
        "SELECT company_id, broad_sector FROM sectors",
        conn,
    )

    conn.close()

    market_cap = pd.read_csv(
        "data/processed/market_cap.csv"
    )

    profit_loss = pd.read_csv(
        "data/processed/profitandloss.csv"
    )

    cagr = pd.read_csv(
        "output/day10_cagr_metrics.csv"
    )

    ratios = clean_company_id(ratios)
    sectors = clean_company_id(sectors)
    market_cap = clean_company_id(market_cap)
    profit_loss = clean_company_id(profit_loss)
    cagr = clean_company_id(cagr)

    # ---------------------------------------------------------
    # Financial ratio history
    # Used to calculate whether D/E declined year-over-year.
    # ---------------------------------------------------------

    ratio_history = ratios[
        ratios["year"].astype(str).str.upper() != "TTM"
    ].copy()

    ratio_history["year_num"] = extract_year_number(
        ratio_history["year"]
    )

    ratio_history = ratio_history.dropna(
        subset=["year_num"]
    )

    ratio_history = ratio_history.sort_values(
        ["company_id", "year_num"]
    )

    ratio_history["previous_debt_to_equity"] = (
        ratio_history
        .groupby("company_id")["debt_to_equity"]
        .shift(1)
    )

    ratio_history["debt_to_equity_declining"] = (
        ratio_history["debt_to_equity"]
        < ratio_history["previous_debt_to_equity"]
    )

    # Keep only the latest annual ratio record per company.
    latest_ratios = (
        ratio_history
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    # ---------------------------------------------------------
    # Latest market-cap record
    # ---------------------------------------------------------

    market_cap["year_num"] = pd.to_numeric(
        market_cap["year"],
        errors="coerce",
    )

    latest_market_cap = (
        market_cap
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    # ---------------------------------------------------------
    # Latest annual P&L record
    # ---------------------------------------------------------

    profit_loss = profit_loss[
        profit_loss["year"].astype(str).str.upper() != "TTM"
    ].copy()

    profit_loss["year_num"] = extract_year_number(
        profit_loss["year"]
    )

    latest_profit_loss = (
        profit_loss
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    # ---------------------------------------------------------
    # Merge all sources
    # ---------------------------------------------------------

    df = latest_ratios.merge(
        sectors[
            [
                "company_id",
                "broad_sector",
            ]
        ],
        on="company_id",
        how="left",
    )

    df = df.merge(
        latest_market_cap[
            [
                "company_id",
                "pe_ratio",
                "pb_ratio",
                "dividend_yield_pct",
                "market_cap_crore",
            ]
        ],
        on="company_id",
        how="left",
    )

    df = df.merge(
        latest_profit_loss[
            [
                "company_id",
                "sales",
                "net_profit",
            ]
        ],
        on="company_id",
        how="left",
    )

    cagr_columns = [
        "company_id",
        "revenue_cagr_3yr",
        "revenue_cagr_3yr_flag",
    ]

    available_cagr_columns = [
        column
        for column in cagr_columns
        if column in cagr.columns
    ]

    df = df.merge(
        cagr[available_cagr_columns],
        on="company_id",
        how="left",
    )

    return df

def apply_filters(df, filters):
    result = df.copy()

    if "roe_min" in filters:
        result = result[
            result["return_on_equity_pct"]
            >= filters["roe_min"]
        ]

    if "debt_to_equity_max" in filters:
        financials = result[
            "broad_sector"
        ].eq("Financials")

        non_financial_pass = (
            result["debt_to_equity"]
            <= filters["debt_to_equity_max"]
        )

        result = result[
            financials | non_financial_pass
        ]

    if "debt_to_equity_equal" in filters:
        result = result[
            result["debt_to_equity"]
            == filters["debt_to_equity_equal"]
        ]

    if "free_cash_flow_min" in filters:
        result = result[
            result["free_cash_flow_cr"]
            > filters["free_cash_flow_min"]
        ]

    if "revenue_cagr_5yr_min" in filters:
        result = result[
            result["revenue_cagr_5yr"]
            >= filters["revenue_cagr_5yr_min"]
        ]

    if "revenue_cagr_3yr_min" in filters:
        result = result[
            result["revenue_cagr_3yr"]
            >= filters["revenue_cagr_3yr_min"]
        ]

    if "pat_cagr_5yr_min" in filters:
        result = result[
            result["pat_cagr_5yr"]
            >= filters["pat_cagr_5yr_min"]
        ]

    if "opm_min" in filters:
        result = result[
            result["operating_profit_margin_pct"]
            >= filters["opm_min"]
        ]

    if "pe_ratio_max" in filters:
        result = result[
            result["pe_ratio"]
            <= filters["pe_ratio_max"]
        ]

    if "pb_ratio_max" in filters:
        result = result[
            result["pb_ratio"]
            <= filters["pb_ratio_max"]
        ]

    if "dividend_yield_min" in filters:
        result = result[
            result["dividend_yield_pct"]
            >= filters["dividend_yield_min"]
        ]

    if "dividend_payout_max" in filters:
        result = result[
            result["dividend_payout_ratio_pct"]
            <= filters["dividend_payout_max"]
        ]

    if "icr_min" in filters:
        # Debt-free companies have null ICR.
        # Treat null ICR as infinity so they pass.
        icr_values = result[
            "interest_coverage"
        ].fillna(float("inf"))

        result = result[
            icr_values >= filters["icr_min"]
        ]

    if "market_cap_min" in filters:
        result = result[
            result["market_cap_crore"]
            >= filters["market_cap_min"]
        ]

    if "net_profit_min" in filters:
        result = result[
            result["net_profit"]
            >= filters["net_profit_min"]
        ]

    if "eps_cagr_min" in filters:
        result = result[
            result["eps_cagr_5yr"]
            >= filters["eps_cagr_min"]
        ]

    if "asset_turnover_min" in filters:
        result = result[
            result["asset_turnover"]
            >= filters["asset_turnover_min"]
        ]

    if "sales_min" in filters:
        result = result[
            result["sales"]
            >= filters["sales_min"]
        ]

    if filters.get(
        "debt_to_equity_declining"
    ) is True:
        result = result[
            result["debt_to_equity_declining"]
            .fillna(False)
        ]

    return result.sort_values(
        "composite_quality_score",
        ascending=False,
    ).reset_index(drop=True)


def run_screener(
    preset_name="quality_compounder",
):
    config = load_config()

    if preset_name not in config:
        raise KeyError(
            f"Preset '{preset_name}' not found "
            "in screener_config.yaml"
        )

    df = load_financial_data()
    df = add_scoring_inputs(df)
    df = add_composite_quality_score(df)

    filters = config[preset_name]

    result = apply_filters(
        df,
        filters,
    )

    return result


if __name__ == "__main__":
    result = run_screener(
        "quality_compounder"
    )

    print(
        "Screener executed successfully"
    )

    print("Rows:", len(result))

    display_columns = [
        "company_id",
        "year",
        "return_on_equity_pct",
        "debt_to_equity",
        "previous_debt_to_equity",
        "debt_to_equity_declining",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "composite_quality_score",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in result.columns
    ]

    print(
        result[available_columns].head(20)
    )