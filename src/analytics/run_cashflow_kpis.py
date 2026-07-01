import sys
import os

sys.path.append(os.path.abspath("."))

import pandas as pd

from src.analytics.cashflow_kpis import (
    free_cash_flow,
    cfo_quality_ratio,
    cfo_quality_label,
    capex_intensity,
    capex_label,
    fcf_conversion_rate,
    sign_value,
    capital_allocation_pattern,
)

cf = pd.read_csv("data/processed/cashflow.csv")
pl = pd.read_csv("data/processed/profitandloss.csv")

cf["company_id"] = cf["company_id"].astype(str).str.strip().str.upper()
pl["company_id"] = pl["company_id"].astype(str).str.strip().str.upper()

merged = cf.merge(
    pl[["company_id", "year", "sales", "net_profit", "operating_profit"]],
    on=["company_id", "year"],
    how="left",
)

merged["free_cash_flow_cr"] = merged.apply(
    lambda row: free_cash_flow(
        row["operating_activity"],
        row["investing_activity"],
    ),
    axis=1,
)

merged["cfo_quality_ratio"] = merged.apply(
    lambda row: cfo_quality_ratio(
        row["operating_activity"],
        row["net_profit"],
    ),
    axis=1,
)

merged["cfo_quality_label"] = merged["cfo_quality_ratio"].apply(
    cfo_quality_label
)

merged["capex_intensity_pct"] = merged.apply(
    lambda row: capex_intensity(
        row["investing_activity"],
        row["sales"],
    ),
    axis=1,
)

merged["capex_label"] = merged["capex_intensity_pct"].apply(capex_label)

merged["fcf_conversion_rate_pct"] = merged.apply(
    lambda row: fcf_conversion_rate(
        row["free_cash_flow_cr"],
        row["operating_profit"],
    ),
    axis=1,
)

merged["cfo_sign"] = merged["operating_activity"].apply(sign_value)
merged["cfi_sign"] = merged["investing_activity"].apply(sign_value)
merged["cff_sign"] = merged["financing_activity"].apply(sign_value)

merged["pattern_label"] = merged.apply(
    lambda row: capital_allocation_pattern(
        row["operating_activity"],
        row["investing_activity"],
        row["financing_activity"],
    ),
    axis=1,
)

output_cols = [
    "company_id",
    "year",
    "free_cash_flow_cr",
    "cfo_quality_ratio",
    "cfo_quality_label",
    "capex_intensity_pct",
    "capex_label",
    "fcf_conversion_rate_pct",
    "cfo_sign",
    "cfi_sign",
    "cff_sign",
    "pattern_label",
]

output = merged[output_cols]

output.to_csv("output/day11_cashflow_kpis.csv", index=False)

capital_allocation = output[
    ["company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "pattern_label"]
]

capital_allocation.to_csv("output/capital_allocation.csv", index=False)

print("Day 11 cash flow KPIs generated successfully")
print("Rows:", len(output))
print(output.head())