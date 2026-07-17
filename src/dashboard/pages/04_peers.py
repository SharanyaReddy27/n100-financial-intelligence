from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_peers,
    get_ratios,
    get_sectors,
)


DB_PATH = "db/nifty100.db"

RADAR_METRICS = {
    "return_on_equity_pct": "ROE",
    "net_profit_margin_pct": "NPM",
    "debt_to_equity": "D/E",
    "free_cash_flow_cr": "FCF",
    "pat_cagr_5yr": "PAT CAGR 5Y",
    "revenue_cagr_5yr": "Revenue CAGR 5Y",
    "interest_coverage": "ICR",
    "asset_turnover": "Asset Turnover",
}


def extract_year_number(series):
    return pd.to_numeric(
        series.astype(str).str.extract(r"(\d{4})")[0],
        errors="coerce",
    )


def get_latest_ratios_for_companies(company_ids):
    if not company_ids:
        return pd.DataFrame()

    placeholders = ",".join(["?"] * len(company_ids))

    query = f"""
        SELECT *
        FROM financial_ratios
        WHERE company_id IN ({placeholders})
          AND UPPER(year) != 'TTM'
    """

    with sqlite3.connect(DB_PATH) as conn:
        ratios = pd.read_sql_query(
            query,
            conn,
            params=company_ids,
        )

    if ratios.empty:
        return ratios

    ratios["year_num"] = extract_year_number(
        ratios["year"]
    )

    ratios = (
        ratios
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    return ratios


def percentile_normalise(series, inverse=False):
    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    ranks = values.rank(
        method="average",
        pct=True,
    ) * 100

    if inverse:
        ranks = 100 - ranks

    return ranks.fillna(0)


def prepare_peer_data(group_name):
    peers = get_peers(group_name)

    if peers.empty:
        return pd.DataFrame()

    company_ids = peers["company_id"].tolist()

    ratios = get_latest_ratios_for_companies(
        company_ids
    )

    companies = get_companies()
    sectors = get_sectors()

    peer_data = peers.merge(
        companies[
            [
                "company_id",
                "company_name",
            ]
        ],
        on="company_id",
        how="left",
    )

    peer_data = peer_data.merge(
        sectors[
            [
                "company_id",
                "broad_sector",
                "sub_sector",
            ]
        ],
        on="company_id",
        how="left",
    )

    peer_data = peer_data.merge(
        ratios,
        on="company_id",
        how="left",
    )

    return peer_data


def add_radar_scores(peer_data):
    data = peer_data.copy()

    for column in RADAR_METRICS:
        inverse = column == "debt_to_equity"

        score_column = f"{column}_radar_score"

        data[score_column] = percentile_normalise(
            data[column],
            inverse=inverse,
        )

    return data


def build_radar_chart(
    selected_row,
    group_average,
):
    categories = list(
        RADAR_METRICS.values()
    )

    company_values = []

    peer_values = []

    for column in RADAR_METRICS:
        score_column = f"{column}_radar_score"

        company_values.append(
            selected_row.get(score_column, 0)
        )

        peer_values.append(
            group_average.get(score_column, 0)
        )

    company_values += company_values[:1]
    peer_values += peer_values[:1]
    categories += categories[:1]

    figure = go.Figure()

    figure.add_trace(
        go.Scatterpolar(
            r=company_values,
            theta=categories,
            fill="toself",
            name=selected_row["company_id"],
        )
    )

    figure.add_trace(
        go.Scatterpolar(
            r=peer_values,
            theta=categories,
            mode="lines",
            line=dict(
                dash="dash",
                width=3,
            ),
            name="Peer Group Average",
        )
    )

    figure.update_layout(
        height=600,
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
            )
        ),
        showlegend=True,
        margin=dict(
            l=40,
            r=40,
            t=60,
            b=40,
        ),
    )

    return figure


def highlight_benchmark(row):
    benchmark = row.get("Benchmark")

    if benchmark is True:
        return [
            "background-color: #D4A017; color: black"
        ] * len(row)

    return [""] * len(row)


def show_peers():
    st.title("Peer Comparison")

    st.caption(
        "Compare a company against its assigned peer group "
        "using percentile-normalised financial metrics."
    )

    all_peers = get_peers()

    if all_peers.empty:
        st.warning(
            "No peer group data is available."
        )
        return

    group_names = sorted(
        all_peers["peer_group_name"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_group = st.selectbox(
        "Select peer group",
        options=group_names,
    )

    peer_data = prepare_peer_data(
        selected_group
    )

    if peer_data.empty:
        st.info(
            "No companies are available in this peer group."
        )
        return

    peer_data = add_radar_scores(
        peer_data
    )

    company_options = (
        peer_data["company_id"]
        + " — "
        + peer_data["company_name"].fillna("")
    ).tolist()

    selected_label = st.selectbox(
        "Select company",
        options=company_options,
    )

    selected_ticker = selected_label.split(
        " — ",
        maxsplit=1,
    )[0]

    selected_rows = peer_data[
        peer_data["company_id"] == selected_ticker
    ]

    if selected_rows.empty:
        st.warning(
            "No peer data is available for the selected company."
        )
        return

    selected_row = selected_rows.iloc[0]

    radar_score_columns = [
        f"{column}_radar_score"
        for column in RADAR_METRICS
    ]

    group_average = peer_data[
        radar_score_columns
    ].mean()

    st.subheader(
        f"{selected_ticker} vs {selected_group} Average"
    )

    radar_chart = build_radar_chart(
        selected_row,
        group_average,
    )

    st.plotly_chart(
        radar_chart,
        use_container_width=True,
    )

    st.subheader(
        f"{selected_group} KPI Comparison"
    )

    table_columns = [
        "company_id",
        "company_name",
        "is_benchmark",
        "return_on_equity_pct",
        "net_profit_margin_pct",
        "debt_to_equity",
        "free_cash_flow_cr",
        "pat_cagr_5yr",
        "revenue_cagr_5yr",
        "interest_coverage",
        "asset_turnover",
        "composite_quality_score",
    ]

    available_columns = [
        column
        for column in table_columns
        if column in peer_data.columns
    ]

    comparison = peer_data[
        available_columns
    ].copy()

    comparison = comparison.rename(
        columns={
            "company_id": "Ticker",
            "company_name": "Company",
            "is_benchmark": "Benchmark",
            "return_on_equity_pct": "ROE %",
            "net_profit_margin_pct": "NPM %",
            "debt_to_equity": "D/E",
            "free_cash_flow_cr": "FCF ₹ Cr",
            "pat_cagr_5yr": "PAT CAGR 5Y %",
            "revenue_cagr_5yr": "Revenue CAGR 5Y %",
            "interest_coverage": "ICR",
            "asset_turnover": "Asset Turnover",
            "composite_quality_score": "Composite Score",
        }
    )

    comparison = comparison.sort_values(
        "Composite Score",
        ascending=False,
        na_position="last",
    )

    styled_comparison = comparison.style.apply(
        highlight_benchmark,
        axis=1,
    )

    st.dataframe(
        styled_comparison,
        use_container_width=True,
        hide_index=True,
    )

    benchmark_rows = comparison[
        comparison["Benchmark"] == True
    ]

    if not benchmark_rows.empty:
        benchmark_ticker = benchmark_rows.iloc[0][
            "Ticker"
        ]

        st.info(
            f"Benchmark company for this group: "
            f"{benchmark_ticker}"
        )


show_peers()