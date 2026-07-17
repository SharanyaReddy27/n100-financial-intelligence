from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_pl,
    get_bs,
    get_cf,
    get_ratios,
)


METRICS = {
    "Revenue": ("pl", "sales"),
    "Net Profit": ("pl", "net_profit"),
    "Operating Profit": ("pl", "operating_profit"),
    "ROE": ("ratios", "return_on_equity_pct"),
    "Net Profit Margin": ("ratios", "net_profit_margin_pct"),
    "Debt to Equity": ("ratios", "debt_to_equity"),
    "Free Cash Flow": ("ratios", "free_cash_flow_cr"),
    "Total Assets": ("bs", "total_assets"),
    "Borrowings": ("bs", "borrowings"),
    "Cash From Operations": ("cf", "operating_activity"),
}


def extract_year_number(series):
    return pd.to_numeric(
        series.astype(str).str.extract(r"(\d{4})")[0],
        errors="coerce",
    )


def prepare_data(df, value_column):
    if df.empty or value_column not in df.columns:
        return pd.DataFrame()

    data = df[
        df["year"].astype(str).str.upper() != "TTM"
    ].copy()

    data["year_num"] = extract_year_number(
        data["year"]
    )

    data[value_column] = pd.to_numeric(
        data[value_column],
        errors="coerce",
    )

    data = (
        data.dropna(
            subset=["year_num", value_column]
        )
        .sort_values("year_num")
        .tail(10)
    )

    data["yoy_change_pct"] = (
        data[value_column]
        .pct_change()
        .mul(100)
    )

    return data


def show_trends():
    st.title("Trend Analysis")

    st.caption(
        "Compare up to three financial metrics across the latest "
        "10 years, including year-over-year changes."
    )

    companies = get_companies()

    companies["search_label"] = (
        companies["company_id"]
        + " — "
        + companies["company_name"].fillna("")
    )

    selected_label = st.selectbox(
        "Select company",
        companies["search_label"].tolist(),
    )

    ticker = selected_label.split(
        " — ",
        maxsplit=1,
    )[0]

    selected_metrics = st.multiselect(
        "Select up to 3 metrics",
        options=list(METRICS.keys()),
        default=["Revenue", "Net Profit"],
        max_selections=3,
    )

    if not selected_metrics:
        st.info("Select at least one metric.")
        return

    datasets = {
        "pl": get_pl(ticker),
        "bs": get_bs(ticker),
        "cf": get_cf(ticker),
        "ratios": get_ratios(ticker),
    }

    figure = go.Figure()
    added_traces = 0

    for metric_name in selected_metrics:
        source_name, value_column = METRICS[
            metric_name
        ]

        data = prepare_data(
            datasets[source_name],
            value_column,
        )

        if data.empty:
            st.info(
                f"{metric_name}: data available for fewer "
                "years or unavailable."
            )
            continue

        hover_text = []

        for _, row in data.iterrows():
            yoy = row["yoy_change_pct"]

            if pd.isna(yoy):
                yoy_text = "YoY: N/A"
            else:
                yoy_text = f"YoY: {yoy:.2f}%"

            hover_text.append(
                f"{metric_name}: {row[value_column]:,.2f}<br>"
                f"{yoy_text}"
            )

        figure.add_trace(
            go.Scatter(
                x=data["year"],
                y=data[value_column],
                mode="lines+markers+text",
                name=metric_name,
                text=[
                    ""
                    if pd.isna(value)
                    else f"{value:.1f}%"
                    for value in data["yoy_change_pct"]
                ],
                textposition="top center",
                hovertext=hover_text,
                hoverinfo="text+x",
            )
        )

        added_traces += 1

    if added_traces == 0:
        st.warning(
            "No usable trend data is available for the selected metrics."
        )
        return

    figure.update_layout(
        height=550,
        xaxis_title="Year",
        yaxis_title="Metric Value",
        hovermode="x unified",
        margin=dict(
            l=20,
            r=20,
            t=40,
            b=20,
        ),
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )


show_trends()