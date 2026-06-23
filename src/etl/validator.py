import pandas as pd
from pathlib import Path

PROCESSED_DIR = Path("data/processed")
OUTPUT_FILE = Path("output/validation_failures.csv")

failures = []

def add_failure(rule, severity, message, company_id="", year=""):
    failures.append({
        "rule": rule,
        "severity": severity,
        "message": message,
        "company_id": company_id,
        "year": year
    })

companies = pd.read_csv(PROCESSED_DIR / "companies.csv")
pl = pd.read_csv(PROCESSED_DIR / "profitandloss.csv")
bs = pd.read_csv(PROCESSED_DIR / "balancesheet.csv")
cf = pd.read_csv(PROCESSED_DIR / "cashflow.csv")
documents = pd.read_csv(PROCESSED_DIR / "documents.csv")
ratios = pd.read_csv(PROCESSED_DIR / "financial_ratios.csv")
sectors = pd.read_csv(PROCESSED_DIR / "sectors.csv")
prices = pd.read_csv(PROCESSED_DIR / "stock_prices.csv")

for df in [companies, pl, bs, cf, documents, ratios, sectors, prices]:
    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()

companies["id"] = companies["id"].astype(str).str.strip().str.upper()
valid_companies = set(companies["id"])

# DQ-01 PK uniqueness
if companies["id"].duplicated().any():
    add_failure("DQ-01", "CRITICAL", "Duplicate company id found")

# DQ-02 company_id-year uniqueness
for name, df in [("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)]:
    dup = df[df.duplicated(["company_id", "year"], keep=False)]
    for _, row in dup.iterrows():
        add_failure("DQ-02", "CRITICAL", f"Duplicate company-year in {name}", row["company_id"], row["year"])

# DQ-03 FK integrity
for name, df in [
    ("profitandloss", pl),
    ("balancesheet", bs),
    ("cashflow", cf),
    ("documents", documents),
    ("financial_ratios", ratios),
    ("sectors", sectors),
    ("stock_prices", prices)
]:
    invalid = df[~df["company_id"].isin(valid_companies)]
    for _, row in invalid.iterrows():
        add_failure("DQ-03", "CRITICAL", f"Invalid company_id in {name}", row["company_id"], row.get("year", ""))

# DQ-04 Balance Sheet balance <1%
bs["diff_pct"] = abs(bs["total_assets"] - bs["total_liabilities"]) / bs["total_assets"].replace(0, pd.NA) * 100
for _, row in bs[bs["diff_pct"] > 1].iterrows():
    add_failure("DQ-04", "WARNING", "Balance sheet mismatch >1%", row["company_id"], row["year"])

# DQ-05 OPM cross-check
pl["calc_opm"] = (pl["operating_profit"] / pl["sales"].replace(0, pd.NA)) * 100
pl["opm_diff"] = abs(pl["calc_opm"] - pl["opm_percentage"])
for _, row in pl[pl["opm_diff"] > 1].iterrows():
    add_failure("DQ-05", "WARNING", "OPM mismatch >1%", row["company_id"], row["year"])

# DQ-06 Positive sales
for _, row in pl[pl["sales"] <= 0].iterrows():
    add_failure("DQ-06", "CRITICAL", "Sales is zero or negative", row["company_id"], row["year"])

# DQ-07 Positive assets
for _, row in bs[bs["total_assets"] <= 0].iterrows():
    add_failure("DQ-07", "CRITICAL", "Total assets zero or negative", row["company_id"], row["year"])

# DQ-08 Positive liabilities
for _, row in bs[bs["total_liabilities"] <= 0].iterrows():
    add_failure("DQ-08", "CRITICAL", "Total liabilities zero or negative", row["company_id"], row["year"])

# DQ-09 Net cash validation
cf["calc_net_cash"] = cf["operating_activity"] + cf["investing_activity"] + cf["financing_activity"]
cf["cash_diff"] = abs(cf["calc_net_cash"] - cf["net_cash_flow"])
for _, row in cf[cf["cash_diff"] > 10].iterrows():
    add_failure("DQ-09", "WARNING", "Net cash flow mismatch >10 Cr", row["company_id"], row["year"])

# DQ-10 Tax rate validation
for _, row in pl[(pl["tax_percentage"] < 0) | (pl["tax_percentage"] > 100)].iterrows():
    add_failure("DQ-10", "WARNING", "Tax percentage outside 0-100", row["company_id"], row["year"])

# DQ-11 Dividend cap validation
for _, row in pl[pl["dividend_payout"] > 150].iterrows():
    add_failure("DQ-11", "WARNING", "Dividend payout unusually high", row["company_id"], row["year"])

# DQ-12 URL validation
for _, row in documents[~documents["Annual_Report"].astype(str).str.startswith("http")].iterrows():
    add_failure("DQ-12", "WARNING", "Invalid annual report URL", row["company_id"], row["Year"])

# DQ-13 EPS sign validation
for _, row in pl[(pl["net_profit"] > 0) & (pl["eps"] <= 0)].iterrows():
    add_failure("DQ-13", "WARNING", "Positive profit but EPS is non-positive", row["company_id"], row["year"])

# DQ-14 Year coverage validation
coverage = pl.groupby("company_id")["year"].nunique()
for company_id, count in coverage.items():
    if count < 5:
        add_failure("DQ-14", "WARNING", "Less than 5 years of P&L data", company_id, "")

# DQ-15 Missing value validation
for name, df in [
    ("companies", companies),
    ("profitandloss", pl),
    ("balancesheet", bs),
    ("cashflow", cf)
]:
    if df.isnull().sum().sum() > 0:
        add_failure("DQ-15", "WARNING", f"Missing values found in {name}")

# DQ-16 Company coverage validation
if len(companies) != 92:
    add_failure("DQ-16", "CRITICAL", f"Company count is {len(companies)}, expected 92")

validation = pd.DataFrame(failures)
validation.to_csv(OUTPUT_FILE, index=False)

print("Validation completed")
print("Total failures:", len(validation))
print(validation.head(20))