import sys
import os

sys.path.append(os.path.abspath("."))

import pandas as pd

from src.analytics.ratios import (
    debt_to_equity,
    high_leverage_flag,
    interest_coverage_ratio,
    icr_label,
    icr_warning_flag,
    net_debt,
    asset_turnover,
)

pl = pd.read_csv("data/processed/profitandloss.csv")
bs = pd.read_csv("data/processed/balancesheet.csv")
sectors = pd.read_csv("data/processed/sectors.csv")

for df in [pl, bs, sectors]:
    df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()

merged = pl.merge(
    bs[
        [
            "company_id",
            "year",
            "equity_capital",
            "reserves",
            "borrowings",
            "investments",
            "total_assets",
        ]
    ],
    on=["company_id", "year"],
    how="left",
)

merged = merged.merge(
    sectors[["company_id", "broad_sector"]],
    on="company_id",
    how="left",
)

merged["debt_to_equity"] = merged.apply(
    lambda row: debt_to_equity(
        row["borrowings"],
        row["equity_capital"],
        row["reserves"],
    ),
    axis=1,
)

merged["high_leverage_flag"] = merged.apply(
    lambda row: high_leverage_flag(
        row["debt_to_equity"],
        row["broad_sector"],
    ),
    axis=1,
)

merged["interest_coverage"] = merged.apply(
    lambda row: interest_coverage_ratio(
        row["operating_profit"],
        row["other_income"],
        row["interest"],
    ),
    axis=1,
)

merged["icr_label"] = merged["interest_coverage"].apply(icr_label)

merged["icr_warning_flag"] = merged["interest_coverage"].apply(
    icr_warning_flag
)

merged["net_debt"] = merged.apply(
    lambda row: net_debt(
        row["borrowings"],
        row["investments"],
    ),
    axis=1,
)

merged["asset_turnover"] = merged.apply(
    lambda row: asset_turnover(
        row["sales"],
        row["total_assets"],
    ),
    axis=1,
)

output_cols = [
    "company_id",
    "year",
    "debt_to_equity",
    "high_leverage_flag",
    "interest_coverage",
    "icr_label",
    "icr_warning_flag",
    "net_debt",
    "asset_turnover",
    "broad_sector",
]

output = merged[output_cols]

output.to_csv("output/day09_leverage_efficiency.csv", index=False)

print("Day 09 leverage and efficiency ratios generated successfully")
print("Rows:", len(output))
print(output.head())