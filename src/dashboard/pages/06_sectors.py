from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_sectors,
)


DB_PATH = "db/nifty100.db"


def extract_year_number(series):
    return pd.to_numeric(
        series.astype(str).str.extract(r"(\d{4})")[0],
        errors="coerce",
    )


@st.cache_data(ttl=600)
def load_sector_analysis_data():
    with sqlite3.connect(DB_PATH) as conn:
        ratios = pd.read_sql_query(
            """
            SELECT *
            FROM financial_ratios
            WHERE UPPER(year) != 'TTM'
            """,
            conn,
        )

        profit_loss = pd.read_sql_query(
            """
            SELECT company_id, year, sales, net_profit
            FROM profitandloss
            WHERE UPPER(year) != 'TTM'
            """,
            conn,
        )

        market_cap = pd.read_sql_query(
            """
            SELECT
                company_id,
                year,
                market_cap_crore,
                pe_ratio,
                pb_ratio,
                dividend_yield_pct
            FROM market_cap
            """,
            conn,
        )

    for dataframe in [ratios, profit_loss, market_cap]:
        dataframe["company_id"] = (
            dataframe["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

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

    profit_loss["year_num"] = extract_year_number(
        profit_loss["year"]
    )

    latest_profit_loss = (
        profit_loss
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    market_cap["year_num"] = pd.to_numeric(
        market_cap["year"],
        errors="coerce",
    )

    latest_market_cap = (
        market_cap
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    companies = get_companies()
    sectors = get_sectors()

    companies["company_id"] = (
        companies["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    sectors["company_id"] = (
        sectors["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    data = sectors.merge(
        companies[
            [
                "company_id",
                "company_name",
            ]
        ],
        on="company_id",
        how="left",
    )

    data = data.merge(
        latest_ratios,
        on="company_id",
        how="left",
    )

    data = data.merge(
        latest_profit_loss[
            [
                "company_id",
                "sales",
                "net_profit",
            ]
        ],
        on="company_id",
        how="left",
    )

    data = data.merge(
        latest_market_cap[
            [
                "company_id",
                "market_cap_crore",
                "pe_ratio",
                "pb_ratio",
                "dividend_yield_pct",
            ]
        ],
        on="company_id",
        how="left",
    )

    return data


def show_sector_analysis():
    st.title("Sector Analysis")

    st.caption(
        "Compare company performance and sector-level median KPIs."
    )

    try:
        data = load_sector_analysis_data()
    except Exception as error:
        st.error(
            f"Unable to load sector analysis data: {error}"
        )
        return

    if data.empty:
        st.warning(
            "Sector analysis data is unavailable."
        )
        return

    sector_options = sorted(
        data["broad_sector"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_sector = st.selectbox(
        "Select sector",
        options=sector_options,
    )

    sector_data = data[
        data["broad_sector"] == selected_sector
    ].copy()

    if sector_data.empty:
        st.info(
            "No companies are available in the selected sector."
        )
        return

    st.subheader(
        f"{selected_sector} Company Map"
    )

    bubble_data = sector_data.dropna(
        subset=[
            "sales",
            "return_on_equity_pct",
            "market_cap_crore",
        ]
    ).copy()

    if bubble_data.empty:
        st.info(
            "Revenue, ROE, or Market Cap data is unavailable "
            "for this sector."
        )
    else:
        bubble_data["bubble_size"] = (
            pd.to_numeric(
                bubble_data["market_cap_crore"],
                errors="coerce",
            )
            .clip(lower=1)
        )

        bubble_chart = px.scatter(
            bubble_data,
            x="sales",
            y="return_on_equity_pct",
            size="bubble_size",
            color="sub_sector",
            hover_name="company_name",
            hover_data={
                "company_id": True,
                "sales": ":,.2f",
                "return_on_equity_pct": ":.2f",
                "market_cap_crore": ":,.2f",
                "bubble_size": False,
            },
            labels={
                "sales": "Revenue (₹ Cr)",
                "return_on_equity_pct": "ROE (%)",
                "sub_sector": "Sub-sector",
            },
            title=(
                "Revenue vs ROE — Bubble Size Represents Market Cap"
            ),
            size_max=65,
        )

        bubble_chart.update_layout(
            height=550,
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=20,
            ),
        )

        st.plotly_chart(
            bubble_chart,
            use_container_width=True,
        )

    st.divider()

    st.subheader(
        "Sector Median KPIs"
    )

    median_metrics = {
        "ROE %": "return_on_equity_pct",
        "Net Profit Margin %": "net_profit_margin_pct",
        "Operating Margin %": "operating_profit_margin_pct",
        "Debt to Equity": "debt_to_equity",
        "Revenue CAGR 5Y %": "revenue_cagr_5yr",
        "PAT CAGR 5Y %": "pat_cagr_5yr",
        "Interest Coverage": "interest_coverage",
        "Asset Turnover": "asset_turnover",
        "P/E": "pe_ratio",
        "P/B": "pb_ratio",
    }

    median_rows = []

    for label, column in median_metrics.items():
        if column not in sector_data.columns:
            continue

        values = pd.to_numeric(
            sector_data[column],
            errors="coerce",
        )

        median_value = values.median()

        if pd.notna(median_value):
            median_rows.append(
                {
                    "Metric": label,
                    "Median Value": median_value,
                }
            )

    median_df = pd.DataFrame(
        median_rows
    )

    if median_df.empty:
        st.info(
            "Median KPI data is unavailable."
        )
    else:
        median_chart = px.bar(
            median_df,
            x="Metric",
            y="Median Value",
            text="Median Value",
            title=f"{selected_sector} Median Financial Metrics",
        )

        median_chart.update_traces(
            texttemplate="%{text:.2f}",
            textposition="outside",
        )

        median_chart.update_layout(
            height=500,
            xaxis_title="",
            yaxis_title="Median Value",
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=80,
            ),
        )

        st.plotly_chart(
            median_chart,
            use_container_width=True,
        )

    st.subheader(
        "Companies in Selected Sector"
    )

    table_columns = [
        "company_id",
        "company_name",
        "sub_sector",
        "sales",
        "return_on_equity_pct",
        "net_profit_margin_pct",
        "debt_to_equity",
        "market_cap_crore",
        "revenue_cagr_5yr",
        "composite_quality_score",
    ]

    available_columns = [
        column
        for column in table_columns
        if column in sector_data.columns
    ]

    company_table = sector_data[
        available_columns
    ].copy()

    company_table = company_table.rename(
        columns={
            "company_id": "Ticker",
            "company_name": "Company",
            "sub_sector": "Sub-sector",
            "sales": "Revenue ₹ Cr",
            "return_on_equity_pct": "ROE %",
            "net_profit_margin_pct": "NPM %",
            "debt_to_equity": "D/E",
            "market_cap_crore": "Market Cap ₹ Cr",
            "revenue_cagr_5yr": "Revenue CAGR 5Y %",
            "composite_quality_score": "Composite Score",
        }
    )

    st.dataframe(
        company_table,
        use_container_width=True,
        hide_index=True,
    )


show_sector_analysis()