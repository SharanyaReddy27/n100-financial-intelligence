import sys
import os

sys.path.append(os.path.abspath("."))
import pandas as pd

from src.analytics.ratios import (
    net_profit_margin,
    operating_profit_margin,
    opm_mismatch_flag,
    return_on_equity,
    return_on_capital_employed,
    return_on_assets,
)

pl = pd.read_csv("data/processed/profitandloss.csv")
bs = pd.read_csv("data/processed/balancesheet.csv")
sectors = pd.read_csv("data/processed/sectors.csv")

pl["company_id"] = pl["company_id"].astype(str).str.strip().str.upper()
bs["company_id"] = bs["company_id"].astype(str).str.strip().str.upper()
sectors["company_id"] = sectors["company_id"].astype(str).str.strip().str.upper()

merged = pl.merge(
    bs[
        [
            "company_id",
            "year",
            "equity_capital",
            "reserves",
            "borrowings",
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

merged["net_profit_margin_pct"] = merged.apply(
    lambda row: net_profit_margin(row["net_profit"], row["sales"]),
    axis=1,
)

merged["operating_profit_margin_pct"] = merged.apply(
    lambda row: operating_profit_margin(row["operating_profit"], row["sales"]),
    axis=1,
)

merged["opm_mismatch_flag"] = merged.apply(
    lambda row: opm_mismatch_flag(
        row["operating_profit_margin_pct"], row["opm_percentage"]
    ),
    axis=1,
)

merged["return_on_equity_pct"] = merged.apply(
    lambda row: return_on_equity(
        row["net_profit"], row["equity_capital"], row["reserves"]
    ),
    axis=1,
)

merged["return_on_capital_employed_pct"] = merged.apply(
    lambda row: return_on_capital_employed(
        row["operating_profit"],
        row["depreciation"],
        row["equity_capital"],
        row["reserves"],
        row["borrowings"],
    ),
    axis=1,
)

merged["return_on_assets_pct"] = merged.apply(
    lambda row: return_on_assets(row["net_profit"], row["total_assets"]),
    axis=1,
)

merged["is_financial_sector"] = merged["broad_sector"].eq("Financials")

output_cols = [
    "company_id",
    "year",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "opm_mismatch_flag",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "return_on_assets_pct",
    "broad_sector",
    "is_financial_sector",
]

output = merged[output_cols]

output.to_csv("output/day08_profitability_ratios.csv", index=False)
opm_mismatches = output[output["opm_mismatch_flag"] == True]

opm_mismatches.to_csv(
    "output/opm_mismatch_log.csv",
    index=False
)

print("OPM mismatch log generated")
print("OPM mismatches:", len(opm_mismatches))

print("Day 08 profitability ratios generated successfully")
print("Rows:", len(output))
print(output.head())