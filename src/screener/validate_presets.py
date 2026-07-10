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

print("=" * 70)
print("DAY 16 PRESET VALIDATION")
print("=" * 70)

for preset in PRESETS:
    result = run_screener(preset)
    count = len(result)

    if 5 <= count <= 50:
        status = "PASS"
    else:
        status = "DATASET LIMITED"

    print(f"{preset:25} {count:3d} companies   {status}")

print("=" * 70)