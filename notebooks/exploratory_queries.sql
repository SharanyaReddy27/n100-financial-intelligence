-- 1. Total companies
SELECT COUNT(*) AS total_companies
FROM companies;

-- 2. Companies by sector
SELECT broad_sector, COUNT(*) AS company_count
FROM sectors
GROUP BY broad_sector
ORDER BY company_count DESC;

-- 3. Top 10 companies by sales
SELECT company_id, year, sales
FROM profitandloss
ORDER BY sales DESC
LIMIT 10;

-- 4. Top 10 companies by net profit
SELECT company_id, year, net_profit
FROM profitandloss
ORDER BY net_profit DESC
LIMIT 10;

-- 5. Highest market cap companies
SELECT company_id, year, market_cap_crore
FROM market_cap
ORDER BY market_cap_crore DESC
LIMIT 10;

-- 6. Top ROE companies
SELECT company_id, year, return_on_equity_pct
FROM financial_ratios
ORDER BY return_on_equity_pct DESC
LIMIT 10;

-- 7. Highest debt-to-equity companies
SELECT company_id, year, debt_to_equity
FROM financial_ratios
ORDER BY debt_to_equity DESC
LIMIT 10;

-- 8. Average PE ratio by year
SELECT year, ROUND(AVG(pe_ratio), 2) AS avg_pe_ratio
FROM market_cap
GROUP BY year
ORDER BY year;

-- 9. Stock price records by company
SELECT company_id, COUNT(*) AS price_records
FROM stock_prices
GROUP BY company_id
ORDER BY price_records DESC
LIMIT 10;

-- 10. Companies with annual reports
SELECT company_id, COUNT(*) AS report_count
FROM documents
GROUP BY company_id
ORDER BY report_count DESC
LIMIT 10;