import sys
import os

sys.path.append(os.path.abspath("."))

import pandas as pd

from src.analytics.cagr import get_cagr_for_window

pl = pd.read_csv("data/processed/profitandloss.csv")

pl["company_id"] = pl["company_id"].astype(str).str.strip().str.upper()

pl["year_num"] = (
    pl["year"]
    .astype(str)
    .str.extract(r"(\d{4})")[0]
    .astype(float)
)

results = []

for company_id in sorted(pl["company_id"].unique()):
    row = {"company_id": company_id}

    for window in [3, 5, 10]:
        revenue_cagr, revenue_flag = get_cagr_for_window(
            pl, company_id, "sales", window
        )

        pat_cagr, pat_flag = get_cagr_for_window(
            pl, company_id, "net_profit", window
        )

        eps_cagr, eps_flag = get_cagr_for_window(
            pl, company_id, "eps", window
        )

        row[f"revenue_cagr_{window}yr"] = revenue_cagr
        row[f"revenue_cagr_{window}yr_flag"] = revenue_flag

        row[f"pat_cagr_{window}yr"] = pat_cagr
        row[f"pat_cagr_{window}yr_flag"] = pat_flag

        row[f"eps_cagr_{window}yr"] = eps_cagr
        row[f"eps_cagr_{window}yr_flag"] = eps_flag

    results.append(row)

output = pd.DataFrame(results)

output.to_csv("output/day10_cagr_metrics.csv", index=False)

print("Day 10 CAGR metrics generated successfully")
print("Rows:", len(output))
print(output.head())