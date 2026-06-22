PRAGMA foreign_keys = ON;

CREATE TABLE companies (
    id TEXT PRIMARY KEY,
    company_name TEXT
);

CREATE TABLE profitandloss (
    id INTEGER PRIMARY KEY,
    company_id TEXT,
    year TEXT,
    sales REAL,
    net_profit REAL,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE balancesheet (
    id INTEGER PRIMARY KEY,
    company_id TEXT,
    year TEXT,
    total_assets REAL,
    total_liabilities REAL,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE cashflow (
    id INTEGER PRIMARY KEY,
    company_id TEXT,
    year TEXT,
    net_cash_flow REAL,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);