import sqlite3
import pandas as pd

DB_PATH = "db/nifty100.db"

tables = {
    "companies": "data/processed/companies.csv",
    "profitandloss": "data/processed/profitandloss.csv",
    "balancesheet": "data/processed/balancesheet.csv",
    "cashflow": "data/processed/cashflow.csv",
    "analysis": "data/processed/analysis.csv",
    "documents": "data/processed/documents.csv",
    "prosandcons": "data/processed/prosandcons.csv",
    "sectors": "data/processed/sectors.csv",
    "stock_prices": "data/processed/stock_prices.csv",
    "financial_ratios": "data/processed/financial_ratios.csv",
    "peer_groups": "data/processed/peer_groups.csv",
    "market_cap": "data/processed/market_cap.csv"
}

conn = sqlite3.connect(DB_PATH)

for table_name, file_path in tables.items():
    df = pd.read_csv(file_path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    print(f"{table_name} loaded: {len(df)} rows")

conn.close()

print("All tables loaded successfully.")