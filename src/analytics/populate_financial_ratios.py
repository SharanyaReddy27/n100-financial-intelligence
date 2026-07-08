import sqlite3
import pandas as pd

DB_PATH = "db/nifty100.db"

day08 = pd.read_csv("output/day08_profitability_ratios.csv")
day09 = pd.read_csv("output/day09_leverage_efficiency.csv")
day10 = pd.read_csv("output/day10_cagr_metrics.csv")
day11 = pd.read_csv("output/day11_cashflow_kpis.csv")
pl = pd.read_csv("data/processed/profitandloss.csv")
bs = pd.read_csv("data/processed/balancesheet.csv")

for df in [day08, day09, day10, day11, pl, bs]:
    df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()

base = day08.merge(
    day09,
    on=["company_id", "year"],
    how="left",
    suffixes=("", "_day09")
)

base = base.merge(
    day11,
    on=["company_id", "year"],
    how="left"
)

base = base.merge(
    day10,
    on="company_id",
    how="left"
)

base = base.merge(
    pl[["company_id", "year", "eps", "dividend_payout"]],
    on=["company_id", "year"],
    how="left"
)

base = base.merge(
    bs[["company_id", "year", "borrowings", "reserves", "equity_capital"]],
    on=["company_id", "year"],
    how="left"
)

base["book_value_per_share"] = base["reserves"] + base["equity_capital"]
base["total_debt_cr"] = base["borrowings"]
base["cash_from_operations_cr"] = base["cfo_quality_ratio"]

base = base.drop_duplicates(subset=["company_id", "year"], keep="first")

final = pd.DataFrame({
    "company_id": base["company_id"],
    "year": base["year"],
    "net_profit_margin_pct": base["net_profit_margin_pct"],
    "operating_profit_margin_pct": base["operating_profit_margin_pct"],
    "return_on_equity_pct": base["return_on_equity_pct"],
    "debt_to_equity": base["debt_to_equity"],
    "interest_coverage": base["interest_coverage"],
    "asset_turnover": base["asset_turnover"],
    "free_cash_flow_cr": base["free_cash_flow_cr"],
    "capex_cr": base["capex_intensity_pct"],
    "earnings_per_share": base["eps"],
    "book_value_per_share": base["book_value_per_share"],
    "dividend_payout_ratio_pct": base["dividend_payout"],
    "total_debt_cr": base["total_debt_cr"],
    "cash_from_operations_cr": base["cash_from_operations_cr"],
    "revenue_cagr_5yr": base["revenue_cagr_5yr"],
    "revenue_cagr_5yr_flag": base["revenue_cagr_5yr_flag"],
    "pat_cagr_5yr": base["pat_cagr_5yr"],
    "pat_cagr_5yr_flag": base["pat_cagr_5yr_flag"],
    "eps_cagr_5yr": base["eps_cagr_5yr"],
    "eps_cagr_5yr_flag": base["eps_cagr_5yr_flag"],
    "composite_quality_score": 0
})

final.insert(0, "id", range(1, len(final) + 1))

conn = sqlite3.connect(DB_PATH)

final.to_sql(
    "financial_ratios",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print("financial_ratios table populated successfully")
print("Rows:", len(final))
print("Columns:", len(final.columns))
print(final.head())