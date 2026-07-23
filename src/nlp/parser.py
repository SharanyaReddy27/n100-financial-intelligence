import re
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ANALYSIS_FILE = PROJECT_ROOT / "data" / "processed" / "analysis.csv"
CAGR_FILE = PROJECT_ROOT / "output" / "day10_cagr_metrics.csv"

OUTPUT_DIR = PROJECT_ROOT / "output"
PARSED_FILE = OUTPUT_DIR / "analysis_parsed.csv"
FAILURES_FILE = OUTPUT_DIR / "parse_failures.csv"
VALIDATION_FILE = OUTPUT_DIR / "cagr_validation.csv"

TARGET_FIELDS = [
    "compounded_sales_growth",
    "compounded_profit_growth",
    "stock_price_cagr",
    "roe",
]

METRIC_NAMES = {
    "compounded_sales_growth": "revenue_cagr",
    "compounded_profit_growth": "pat_cagr",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}

# Supports:
# 10 Years: 21%
# 5 Years 14.5%
# 3 Year: -2%
PATTERN = re.compile(
    r"(\d+)\s*Years?\s*:?\s*(-?[\d.]+)\s*%",
    re.IGNORECASE,
)


def clean_company_id(value):
    return str(value).strip().upper()


def parse_analysis(analysis):
    parsed_records = []
    failure_records = []

    for _, row in analysis.iterrows():
        company_id = clean_company_id(row["company_id"])

        for field in TARGET_FIELDS:
            raw_value = row.get(field)

            if pd.isna(raw_value):
                failure_records.append(
                    {
                        "company_id": company_id,
                        "metric_type": METRIC_NAMES[field],
                        "original_text": "",
                        "failure_reason": "Missing value",
                    }
                )
                continue

            text = str(raw_value).strip()
            match = PATTERN.search(text)

            if not match:
                failure_records.append(
                    {
                        "company_id": company_id,
                        "metric_type": METRIC_NAMES[field],
                        "original_text": text,
                        "failure_reason": "Regex pattern not matched",
                    }
                )
                continue

            try:
                period_years = int(match.group(1))
                value_pct = float(match.group(2))
            except ValueError:
                failure_records.append(
                    {
                        "company_id": company_id,
                        "metric_type": METRIC_NAMES[field],
                        "original_text": text,
                        "failure_reason": "Unable to convert parsed value",
                    }
                )
                continue

            parsed_records.append(
                {
                    "company_id": company_id,
                    "metric_type": METRIC_NAMES[field],
                    "period_years": period_years,
                    "value_pct": value_pct,
                }
            )

    parsed_df = pd.DataFrame(
        parsed_records,
        columns=[
            "company_id",
            "metric_type",
            "period_years",
            "value_pct",
        ],
    )

    failures_df = pd.DataFrame(
        failure_records,
        columns=[
            "company_id",
            "metric_type",
            "original_text",
            "failure_reason",
        ],
    )

    return parsed_df, failures_df


def get_computed_column(metric_type, period_years):
    mapping = {
        ("revenue_cagr", 3): "revenue_cagr_3yr",
        ("revenue_cagr", 5): "revenue_cagr_5yr",
        ("revenue_cagr", 10): "revenue_cagr_10yr",
        ("pat_cagr", 3): "pat_cagr_3yr",
        ("pat_cagr", 5): "pat_cagr_5yr",
        ("pat_cagr", 10): "pat_cagr_10yr",
    }

    return mapping.get((metric_type, period_years))


def cross_validate(parsed_df, cagr_df):
    cagr_df = cagr_df.copy()
    cagr_df["company_id"] = (
        cagr_df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    cagr_lookup = cagr_df.set_index("company_id")

    validation_records = []

    for _, row in parsed_df.iterrows():
        company_id = row["company_id"]
        metric_type = row["metric_type"]
        period_years = int(row["period_years"])
        parsed_value = float(row["value_pct"])

        computed_column = get_computed_column(
            metric_type,
            period_years,
        )

        # ROE and stock-price CAGR do not have matching fields
        # in day10_cagr_metrics.csv.
        if computed_column is None:
            continue

        if company_id not in cagr_lookup.index:
            validation_records.append(
                {
                    "company_id": company_id,
                    "metric_type": metric_type,
                    "period_years": period_years,
                    "parsed_value_pct": parsed_value,
                    "computed_value_pct": None,
                    "absolute_divergence_pct": None,
                    "review_required": True,
                    "validation_status": "Company not found",
                }
            )
            continue

        computed_value = cagr_lookup.loc[
            company_id,
            computed_column,
        ]

        if isinstance(computed_value, pd.Series):
            computed_value = computed_value.iloc[0]

        if pd.isna(computed_value):
            validation_records.append(
                {
                    "company_id": company_id,
                    "metric_type": metric_type,
                    "period_years": period_years,
                    "parsed_value_pct": parsed_value,
                    "computed_value_pct": None,
                    "absolute_divergence_pct": None,
                    "review_required": True,
                    "validation_status": "Computed CAGR unavailable",
                }
            )
            continue

        computed_value = float(computed_value)
        divergence = abs(parsed_value - computed_value)

        validation_records.append(
            {
                "company_id": company_id,
                "metric_type": metric_type,
                "period_years": period_years,
                "parsed_value_pct": round(parsed_value, 4),
                "computed_value_pct": round(computed_value, 4),
                "absolute_divergence_pct": round(divergence, 4),
                "review_required": divergence > 5,
                "validation_status": (
                    "Manual review"
                    if divergence > 5
                    else "Within tolerance"
                ),
            }
        )

    return pd.DataFrame(
        validation_records,
        columns=[
            "company_id",
            "metric_type",
            "period_years",
            "parsed_value_pct",
            "computed_value_pct",
            "absolute_divergence_pct",
            "review_required",
            "validation_status",
        ],
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not ANALYSIS_FILE.exists():
        raise FileNotFoundError(
            f"Analysis file not found: {ANALYSIS_FILE}"
        )

    if not CAGR_FILE.exists():
        raise FileNotFoundError(
            f"CAGR file not found: {CAGR_FILE}"
        )

    analysis = pd.read_csv(ANALYSIS_FILE)
    cagr = pd.read_csv(CAGR_FILE)

    missing_columns = [
        column
        for column in ["company_id", *TARGET_FIELDS]
        if column not in analysis.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing analysis columns: {missing_columns}"
        )

    parsed_df, failures_df = parse_analysis(analysis)
    validation_df = cross_validate(parsed_df, cagr)

    parsed_df.to_csv(PARSED_FILE, index=False)
    failures_df.to_csv(FAILURES_FILE, index=False)
    validation_df.to_csv(VALIDATION_FILE, index=False)

    review_count = (
        int(validation_df["review_required"].sum())
        if not validation_df.empty
        else 0
    )

    print("=" * 55)
    print("DAY 29 - NLP ANALYSIS PARSER")
    print("=" * 55)
    print(f"Source rows             : {len(analysis)}")
    print(f"Unique source companies : {analysis['company_id'].nunique()}")
    print(f"Parsed records          : {len(parsed_df)}")
    print(f"Parse failures          : {len(failures_df)}")
    print(f"Validation records      : {len(validation_df)}")
    print(f"Manual-review flags     : {review_count}")
    print()
    print(f"Created: {PARSED_FILE}")
    print(f"Created: {FAILURES_FILE}")
    print(f"Created: {VALIDATION_FILE}")


if __name__ == "__main__":
    main()