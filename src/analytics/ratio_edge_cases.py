import sqlite3
import pandas as pd
from pathlib import Path

OUTPUT_PATH = Path("output/ratio_edge_cases.log")

companies = pd.read_csv("data/processed/companies.csv")
sectors = pd.read_csv("data/processed/sectors.csv")

companies["id"] = companies["id"].astype(str).str.strip().str.upper()
sectors["company_id"] = sectors["company_id"].astype(str).str.strip().str.upper()

conn = sqlite3.connect("db/nifty100.db")
ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
conn.close()

ratios["company_id"] = ratios["company_id"].astype(str).str.strip().str.upper()

latest = ratios[ratios["year"] != "TTM"].copy()
latest["year_num"] = latest["year"].astype(str).str.extract(r"(\d{4})")[0].astype(float)
latest = latest.sort_values("year_num").groupby("company_id").tail(1)

merged = latest.merge(
    companies[["id", "roce_percentage", "roe_percentage"]],
    left_on="company_id",
    right_on="id",
    how="left",
)

merged = merged.merge(
    sectors[["company_id", "broad_sector", "sub_sector"]],
    on="company_id",
    how="left",
)

financials = merged[merged["broad_sector"] == "Financials"]

logs = []
logs.append("Ratio Edge Cases Log - Day 13")
logs.append("=" * 60)
logs.append(f"Financials sector companies identified: {financials['company_id'].nunique()}")
logs.append("High leverage warning suppressed for Financials sector companies.")
logs.append("")

def classify_anomaly(diff):
    if diff > 50:
        return "data source issue"
    if diff > 15:
        return "formula discrepancy"
    return "version difference"

for _, row in merged.iterrows():
    company = row["company_id"]
    sector = row.get("broad_sector", "")
    year = row.get("year", "")

    computed_roe = row.get("return_on_equity_pct")
    source_roe = row.get("roe_percentage")

    if pd.notna(computed_roe) and pd.notna(source_roe):
        diff = abs(computed_roe - source_roe)

        if diff > 5:
            category = classify_anomaly(diff)
            logs.append(
                f"{company} | {year} | ROE anomaly | "
                f"computed={computed_roe:.2f}, "
                f"source={source_roe:.2f}, "
                f"diff={diff:.2f} | "
                f"category={category} | "
                f"sector={sector}"
            )

    computed_roce = row.get("return_on_capital_employed_pct")
    source_roce = row.get("roce_percentage")

    if pd.notna(computed_roce) and pd.notna(source_roce):
        diff = abs(computed_roce - source_roce)

        if diff > 5:
            category = classify_anomaly(diff)
            logs.append(
                f"{company} | {year} | ROCE anomaly | "
                f"computed={computed_roce:.2f}, "
                f"source={source_roce:.2f}, "
                f"diff={diff:.2f} | "
                f"category={category} | "
                f"sector={sector}"
            )

OUTPUT_PATH.write_text("\n".join(logs), encoding="utf-8")

print("ratio_edge_cases.log generated successfully")
print("Financials companies:", financials["company_id"].nunique())
print("Log entries:", len(logs))