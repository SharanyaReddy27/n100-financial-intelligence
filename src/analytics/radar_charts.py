import os
import sqlite3
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath("."))


DB_PATH = "db/nifty100.db"
OUTPUT_DIR = "reports/radar_charts"


RADAR_METRICS = {
    "return_on_equity_pct": "ROE",
    "return_on_capital_employed_pct": "ROCE",
    "net_profit_margin_pct": "NPM",
    "debt_to_equity": "D/E",
    "free_cash_flow_cr": "FCF",
    "pat_cagr_5yr": "PAT CAGR",
    "revenue_cagr_5yr": "Revenue CAGR",
    "composite_quality_score": "Quality Score",
}


def load_data():
    conn = sqlite3.connect(DB_PATH)

    percentiles = pd.read_sql_query(
        "SELECT * FROM peer_percentiles",
        conn,
    )

    peer_groups = pd.read_sql_query(
        """
        SELECT company_id, peer_group_name
        FROM peer_groups
        """,
        conn,
    )

    ratios = pd.read_sql_query(
        "SELECT * FROM financial_ratios",
        conn,
    )

    conn.close()

    for df in [percentiles, peer_groups, ratios]:
        df["company_id"] = (
            df["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    ratios = ratios[
        ratios["year"].astype(str).str.upper() != "TTM"
    ].copy()

    ratios["year_num"] = pd.to_numeric(
        ratios["year"]
        .astype(str)
        .str.extract(r"(\d{4})")[0],
        errors="coerce",
    )

    latest_ratios = (
        ratios
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    return percentiles, peer_groups, latest_ratios


def build_company_percentiles(percentiles, latest_ratios):
    pivot = percentiles.pivot_table(
        index=["company_id", "peer_group_name"],
        columns="metric",
        values="percentile_rank",
        aggfunc="first",
    ).reset_index()

    score = latest_ratios[
        ["company_id", "composite_quality_score"]
    ].copy()

    score["composite_quality_score"] = (
        pd.to_numeric(
            score["composite_quality_score"],
            errors="coerce",
        )
        .fillna(0)
        .clip(0, 100)
        / 100
    )

    pivot = pivot.merge(
        score,
        on="company_id",
        how="left",
    )

    return pivot


def prepare_radar_values(row):
    values = []

    for metric in RADAR_METRICS:
        value = row.get(metric, np.nan)

        if pd.isna(value):
            value = 0

        values.append(float(value))

    return values


def create_radar_chart(company_row, peer_average):
    labels = list(RADAR_METRICS.values())

    company_values = prepare_radar_values(company_row)
    average_values = prepare_radar_values(peer_average)

    angles = np.linspace(
        0,
        2 * np.pi,
        len(labels),
        endpoint=False,
    ).tolist()

    company_values += company_values[:1]
    average_values += average_values[:1]
    angles += angles[:1]

    figure = plt.figure(figsize=(8, 8))
    axis = figure.add_subplot(111, polar=True)

    axis.plot(
        angles,
        company_values,
        linewidth=2,
        label=company_row["company_id"],
    )

    axis.fill(
        angles,
        company_values,
        alpha=0.25,
    )

    axis.plot(
        angles,
        average_values,
        linewidth=2,
        linestyle="--",
        label="Peer Average",
    )

    axis.set_xticks(angles[:-1])
    axis.set_xticklabels(labels, fontsize=10)

    axis.set_ylim(0, 1)
    axis.set_yticks([0.25, 0.5, 0.75, 1.0])
    axis.set_yticklabels(
        ["25", "50", "75", "100"],
        fontsize=8,
    )

    axis.set_title(
        f"{company_row['company_id']} — "
        f"{company_row['peer_group_name']}",
        fontsize=14,
        pad=20,
    )

    axis.legend(
        loc="upper right",
        bbox_to_anchor=(1.3, 1.1),
    )

    output_path = os.path.join(
        OUTPUT_DIR,
        f"{company_row['company_id']}_radar.png",
    )

    plt.tight_layout()
    plt.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )
    plt.close()


def main():
    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    percentiles, peer_groups, latest_ratios = load_data()

    radar_data = build_company_percentiles(
        percentiles,
        latest_ratios,
    )

    generated = 0

    for peer_group_name, group in radar_data.groupby(
        "peer_group_name"
    ):
        metric_columns = list(RADAR_METRICS.keys())

        peer_average = group[
            metric_columns
        ].mean(numeric_only=True)

        for _, company_row in group.iterrows():
            create_radar_chart(
                company_row,
                peer_average,
            )

            generated += 1

    print("Radar chart generation completed successfully")
    print("Charts generated:", generated)
    print("Saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()