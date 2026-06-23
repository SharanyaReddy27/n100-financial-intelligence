import sqlite3

conn = sqlite3.connect("db/nifty100.db")

tables = [
    "companies",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "analysis",
    "documents",
    "prosandcons",
    "sectors",
    "stock_prices",
    "financial_ratios",
    "peer_groups",
    "market_cap"
]

for table in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(table, count)

print("\nFK Check:")
print(conn.execute("PRAGMA foreign_key_check").fetchall())

conn.close()