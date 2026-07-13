import os
import sqlite3
import sys

import pandas as pd

sys.path.append(os.path.abspath("."))


DB_PATH = "db/nifty100.db"
OUTPUT_PATH = "output/peer_percentiles.csv"


METRICS = {
    "return_on_equity_pct": False,
    "return_on_capital_employed_pct": False,
    "net_profit_margin_pct": False,
    "debt_to_equity": True,
    "free_cash_flow_cr": False,
    "pat_cagr_5yr": False,
    "revenue_cagr_5yr": False,
    "eps_cagr_5yr": False,
    "interest_coverage": False,
    "asset_turnover": False,
}


def clean_company_id(df):
    df = df.copy()

    if "company_id" in df.columns:
        df["company_id"] = (
            df["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    return df


def extract_year_number(series):
    return pd.to_numeric(
        series.astype(str).str.extract(r"(\d{4})")[0],
        errors="coerce",
    )


def load_peer_data():
    conn = sqlite3.connect(DB_PATH)

    ratios = pd.read_sql_query(
        "SELECT * FROM financial_ratios",
        conn,
    )

    peer_groups = pd.read_sql_query(
        "SELECT company_id, peer_group_name, is_benchmark FROM peer_groups",
        conn,
    )

    conn.close()

    roce = pd.read_csv(
        "output/day08_profitability_ratios.csv"
    )

    ratios = clean_company_id(ratios)
    peer_groups = clean_company_id(peer_groups)
    roce = clean_company_id(roce)

    ratios = ratios[
        ratios["year"].astype(str).str.upper() != "TTM"
    ].copy()

    ratios["year_num"] = extract_year_number(
        ratios["year"]
    )

    latest_ratios = (
        ratios
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    roce = roce[
        roce["year"].astype(str).str.upper() != "TTM"
    ].copy()

    roce["year_num"] = extract_year_number(
        roce["year"]
    )

    latest_roce = (
        roce
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    df = peer_groups.merge(
        latest_ratios,
        on="company_id",
        how="left",
    )

    df = df.merge(
        latest_roce[
            [
                "company_id",
                "return_on_capital_employed_pct",
            ]
        ],
        on="company_id",
        how="left",
    )

    return df


def compute_percentile_ranks(df):
    output_rows = []

    for peer_group_name, group in df.groupby(
        "peer_group_name"
    ):
        for metric, inverse in METRICS.items():
            values = pd.to_numeric(
                group[metric],
                errors="coerce",
            )

            if values.notna().sum() == 0:
                continue

            percentile = values.rank(
                method="min",
                pct=True,
            )

            if inverse:
                percentile = 1 - percentile + (
                    1 / values.notna().sum()
                )

            percentile = percentile.clip(
                0,
                1,
            )

            for index, row in group.iterrows():
                value = values.loc[index]

                if pd.isna(value):
                    continue

                output_rows.append(
                    {
                        "company_id": row["company_id"],
                        "peer_group_name": peer_group_name,
                        "metric": metric,
                        "value": value,
                        "percentile_rank": round(
                            float(percentile.loc[index]),
                            4,
                        ),
                        "year": row["year"],
                    }
                )

    return pd.DataFrame(output_rows)


def save_outputs(percentiles):
    percentiles.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    conn = sqlite3.connect(DB_PATH)

    percentiles.to_sql(
        "peer_percentiles",
        conn,
        if_exists="replace",
        index=False,
    )

    conn.close()


def validate_peer_groups(df):
    peer_group_count = df[
        "peer_group_name"
    ].nunique()

    unassigned = df[
        df["peer_group_name"].isna()
    ]

    print("Peer groups found:", peer_group_count)

    if unassigned.empty:
        print("All companies in this dataset have a peer group.")
    else:
        print(
            "No peer group assigned:",
            unassigned["company_id"].tolist(),
        )


def main():
    peer_data = load_peer_data()

    validate_peer_groups(peer_data)

    percentiles = compute_percentile_ranks(
        peer_data
    )

    save_outputs(percentiles)

    print(
        "Peer percentile calculation completed successfully"
    )

    print("Rows:", len(percentiles))

    print(
        "Peer groups:",
        percentiles["peer_group_name"].nunique(),
    )

    print(percentiles.head(20))


if __name__ == "__main__":
    main()