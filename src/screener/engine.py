import sys
import os

sys.path.append(os.path.abspath("."))

import sqlite3
import pandas as pd
import yaml


def load_config(config_path="config/screener_config.yaml"):
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_financial_data(db_path="db/nifty100.db"):
    conn = sqlite3.connect(db_path)

    ratios = pd.read_sql_query(
        "SELECT * FROM financial_ratios",
        conn
    )

    sectors = pd.read_sql_query(
        "SELECT company_id, broad_sector FROM sectors",
        conn
    )

    conn.close()

    ratios["company_id"] = ratios["company_id"].astype(str).str.strip().str.upper()
    sectors["company_id"] = sectors["company_id"].astype(str).str.strip().str.upper()

    df = ratios.merge(sectors, on="company_id", how="left")

    df = df[df["year"] != "TTM"].copy()

    df["year_num"] = (
        df["year"]
        .astype(str)
        .str.extract(r"(\d{4})")[0]
        .astype(int)
    )

    df = (
        df.sort_values("year_num")
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    df.drop(columns=["year_num"], inplace=True)

    return df


def add_composite_quality_score(df):
    score = 0

    score += df["return_on_equity_pct"].fillna(0).clip(0, 30) / 30 * 30
    score += df["net_profit_margin_pct"].fillna(0).clip(0, 25) / 25 * 20
    score += df["revenue_cagr_5yr"].fillna(0).clip(0, 25) / 25 * 20
    score += (1 - df["debt_to_equity"].fillna(5).clip(0, 5) / 5) * 15
    score += df["free_cash_flow_cr"].fillna(0).gt(0).astype(int) * 15

    df["composite_quality_score"] = score.round(2)

    return df


def apply_filters(df, filters):
    result = df.copy()

    if "roe_min" in filters:
        result = result[result["return_on_equity_pct"] > filters["roe_min"]]

    if "debt_to_equity_max" in filters:
        financials = result["broad_sector"] == "Financials"
        non_financial_pass = result["debt_to_equity"] < filters["debt_to_equity_max"]
        result = result[financials | non_financial_pass]

    if "free_cash_flow_min" in filters:
        result = result[result["free_cash_flow_cr"] > filters["free_cash_flow_min"]]

    if "revenue_cagr_5yr_min" in filters:
        result = result[result["revenue_cagr_5yr"] > filters["revenue_cagr_5yr_min"]]

    if "pat_cagr_5yr_min" in filters:
        result = result[result["pat_cagr_5yr"] > filters["pat_cagr_5yr_min"]]

    if "opm_min" in filters:
        result = result[result["operating_profit_margin_pct"] > filters["opm_min"]]

    if "icr_min" in filters:
        icr_value = result["interest_coverage"].fillna(float("inf"))
        result = result[icr_value > filters["icr_min"]]

    if "asset_turnover_min" in filters:
        result = result[result["asset_turnover"] > filters["asset_turnover_min"]]

    return result.sort_values(
        "composite_quality_score",
        ascending=False
    )


def run_screener(preset_name="quality_compounder"):
    config = load_config()
    df = load_financial_data()
    df = add_composite_quality_score(df)

    filters = config[preset_name]

    result = apply_filters(df, filters)

    return result


if __name__ == "__main__":
    result = run_screener("quality_compounder")

    print("Screener executed successfully")
    print("Rows:", len(result))
    print(result[[
        "company_id",
        "year",
        "return_on_equity_pct",
        "debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "composite_quality_score"
    ]].head(20))