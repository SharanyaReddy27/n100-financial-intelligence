import sys
import os

sys.path.append(os.path.abspath("."))

from src.screener.engine import run_screener

PRESETS = [
    "quality_compounder",
    "value_pick",
    "growth_accelerator",
    "dividend_champion",
    "debt_free_blue_chip",
    "turnaround_watch",
]

for preset in PRESETS:
    result = run_screener(preset)

    print("\n" + "=" * 60)
    print("PRESET:", preset)
    print("Companies:", len(result))

    columns = [
        "company_id",
        "year",
        "return_on_equity_pct",
        "debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "composite_quality_score",
    ]

    available = [
        column for column in columns
        if column in result.columns
    ]

    print(result[available].head(10))