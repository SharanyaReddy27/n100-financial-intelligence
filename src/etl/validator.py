import pandas as pd

companies = pd.read_csv("data/processed/companies.csv")
profitandloss = pd.read_csv("data/processed/profitandloss.csv")

companies["id"] = companies["id"].astype(str).str.strip().str.upper()
profitandloss["company_id"] = profitandloss["company_id"].astype(str).str.strip().str.upper()
profitandloss["year"] = profitandloss["year"].astype(str).str.strip()

failures = []

# DQ-01 Company primary key uniqueness
duplicate_companies = companies[companies["id"].duplicated(keep=False)]

for _, row in duplicate_companies.iterrows():
    failures.append([
        "DQ-01",
        "CRITICAL",
        "Duplicate company ID in companies table",
        row["id"],
        ""
    ])

# DQ-02 Duplicate company-year in Profit & Loss
duplicate_pl = profitandloss[
    profitandloss.duplicated(["company_id", "year"], keep=False)
]

for _, row in duplicate_pl.iterrows():
    failures.append([
        "DQ-02",
        "CRITICAL",
        "Duplicate company-year row in profitandloss table",
        row["company_id"],
        row["year"]
    ])

# DQ-03 Foreign key integrity
valid_companies = set(companies["id"])

invalid_pl = profitandloss[
    ~profitandloss["company_id"].isin(valid_companies)
]

for _, row in invalid_pl.iterrows():
    failures.append([
        "DQ-03",
        "CRITICAL",
        "company_id not found in companies table",
        row["company_id"],
        row["year"]
    ])

validation = pd.DataFrame(
    failures,
    columns=["rule", "severity", "message", "company_id", "year"]
)

validation.to_csv(
    "output/validation_failures.csv",
    index=False
)

print("Validation completed")
print("Total failures:", len(validation))
print(validation.head(20))