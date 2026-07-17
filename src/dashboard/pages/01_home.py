from pathlib import Path
import sys

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_home_data


def format_number(value, suffix=""):
    """Format numbers safely for dashboard cards."""
    if value is None or pd.isna(value):
        return "N/A"

    return f"{float(value):,.2f}{suffix}"


def calculate_quality_score(data):
    """
    Calculate a year-specific quality score from available metrics.

    This keeps the Home page responsive to the selected year and avoids
    relying on the zero-valued score currently stored in SQLite.
    """
    data = data.copy()

    roe = pd.to_numeric(
        data["return_on_equity_pct"],
        errors="coerce",
    ).clip(lower=0, upper=100)

    npm = pd.to_numeric(
        data["net_profit_margin_pct"],
        errors="coerce",
    ).clip(lower=0, upper=50)

    revenue_growth = pd.to_numeric(
        data["revenue_cagr_5yr"],
        errors="coerce",
    ).clip(lower=0, upper=50)

    debt_to_equity = pd.to_numeric(
        data["debt_to_equity"],
        errors="coerce",
    ).clip(lower=0, upper=5)

    positive_fcf = (
        pd.to_numeric(
            data["free_cash_flow_cr"],
            errors="coerce",
        )
        .fillna(0)
        .gt(0)
        .astype(int)
    )

    score = (
        roe.fillna(0) / 100 * 30
        + npm.fillna(0) / 50 * 20
        + revenue_growth.fillna(0) / 50 * 20
        + (1 - debt_to_equity.fillna(5) / 5) * 15
        + positive_fcf * 15
    )

    data["composite_quality_score"] = (
        score.clip(lower=0, upper=100).round(2)
    )

    return data


def show_home():
    st.title("Nifty 100 Financial Intelligence")

    st.caption(
        "Financial analytics, screening and peer intelligence "
        "for Nifty 100 companies"
    )

    selected_year = st.sidebar.selectbox(
        "Select financial year",
        options=[2024, 2023, 2022, 2021, 2020, 2019],
        index=0,
        key="home_year_selector",
    )

    try:
        ratios, market_cap, sectors, companies = get_home_data(
            selected_year
        )
    except Exception as error:
        st.error(f"Unable to load dashboard data: {error}")
        return

    if ratios.empty:
        st.warning(
            f"No financial-ratio data is available for {selected_year}."
        )
        return

    # Clean ticker values
    for dataframe in [ratios, sectors, companies]:
        if "company_id" in dataframe.columns:
            dataframe["company_id"] = (
                dataframe["company_id"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

    if not market_cap.empty:
        market_cap["company_id"] = (
            market_cap["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    # Keep one financial-ratio row for each company
    ratios = ratios.drop_duplicates(
        subset=["company_id"],
        keep="last",
    )

    # Keep one sector row for each company
    sectors = sectors.drop_duplicates(
        subset=["company_id"],
        keep="last",
    )

    # Keep one company row for each ticker
    companies = companies.drop_duplicates(
        subset=["company_id"],
        keep="last",
    )

    dashboard_data = ratios.merge(
        sectors,
        on="company_id",
        how="left",
    )

    dashboard_data = dashboard_data.merge(
        companies,
        on="company_id",
        how="left",
    )

    if not market_cap.empty:
        market_cap = market_cap.drop_duplicates(
            subset=["company_id"],
            keep="last",
        )

        dashboard_data = dashboard_data.merge(
            market_cap[
                [
                    "company_id",
                    "pe_ratio",
                    "pb_ratio",
                    "market_cap_crore",
                    "dividend_yield_pct",
                ]
            ],
            on="company_id",
            how="left",
        )
    else:
        dashboard_data["pe_ratio"] = pd.NA
        dashboard_data["pb_ratio"] = pd.NA
        dashboard_data["market_cap_crore"] = pd.NA
        dashboard_data["dividend_yield_pct"] = pd.NA

    dashboard_data = dashboard_data.drop_duplicates(
        subset=["company_id"],
        keep="last",
    )

    # Calculate a meaningful year-specific quality score
    dashboard_data = calculate_quality_score(
        dashboard_data
    )

    # Remove extreme ROE values before calculating the average
    valid_roe = pd.to_numeric(
        dashboard_data["return_on_equity_pct"],
        errors="coerce",
    )

    valid_roe = valid_roe[
        valid_roe.between(0, 100)
    ]

    average_roe = valid_roe.mean()

    median_pe = pd.to_numeric(
        dashboard_data["pe_ratio"],
        errors="coerce",
    ).median()

    median_de = pd.to_numeric(
        dashboard_data["debt_to_equity"],
        errors="coerce",
    ).median()

    median_revenue_cagr = pd.to_numeric(
        dashboard_data["revenue_cagr_5yr"],
        errors="coerce",
    ).median()

    # Sectors table represents the supported Nifty universe
    total_companies = sectors["company_id"].nunique()

    debt_free_count = (
        pd.to_numeric(
            dashboard_data["debt_to_equity"],
            errors="coerce",
        )
        .fillna(-1)
        .eq(0)
        .sum()
    )

    st.subheader(f"Market Overview — {selected_year}")

    first_row = st.columns(3)

    first_row[0].metric(
        "Average ROE",
        format_number(average_roe, "%"),
    )

    first_row[1].metric(
        "Median P/E",
        format_number(median_pe),
    )

    first_row[2].metric(
        "Median D/E",
        format_number(median_de),
    )

    second_row = st.columns(3)

    second_row[0].metric(
        "Total Companies",
        str(total_companies),
    )

    second_row[1].metric(
        "Median Revenue CAGR 5Y",
        format_number(
            median_revenue_cagr,
            "%",
        ),
    )

    second_row[2].metric(
        "Debt-Free Companies",
        str(int(debt_free_count)),
    )

    st.divider()

    left_column, right_column = st.columns(
        [1.1, 1],
        gap="large",
    )

    with left_column:
        st.subheader("Sector Breakdown")

        sector_counts = (
            sectors[
                sectors["broad_sector"].notna()
            ]
            .groupby("broad_sector")["company_id"]
            .nunique()
            .reset_index(name="company_count")
            .sort_values(
                "company_count",
                ascending=False,
            )
        )

        if sector_counts.empty:
            st.info("Sector information is unavailable.")
        else:
            donut_chart = px.pie(
                sector_counts,
                names="broad_sector",
                values="company_count",
                hole=0.55,
                title="Companies by Broad Sector",
            )

            donut_chart.update_traces(
                textposition="inside",
                textinfo="percent+label",
            )

            donut_chart.update_layout(
                height=500,
                margin=dict(
                    l=10,
                    r=10,
                    t=60,
                    b=10,
                ),
                legend_title_text="Sector",
            )

            st.plotly_chart(
                donut_chart,
                use_container_width=True,
            )

    with right_column:
        st.subheader("Top 5 Quality Companies")

        required_columns = [
            "company_id",
            "company_name",
            "broad_sector",
            "return_on_equity_pct",
            "revenue_cagr_5yr",
            "debt_to_equity",
            "composite_quality_score",
        ]

        available_columns = [
            column
            for column in required_columns
            if column in dashboard_data.columns
        ]

        top_companies = (
            dashboard_data[available_columns]
            .sort_values(
                "composite_quality_score",
                ascending=False,
            )
            .head(5)
            .copy()
        )

        top_companies = top_companies.rename(
            columns={
                "company_id": "Ticker",
                "company_name": "Company",
                "broad_sector": "Sector",
                "return_on_equity_pct": "ROE %",
                "revenue_cagr_5yr": "Revenue CAGR 5Y %",
                "debt_to_equity": "D/E",
                "composite_quality_score": "Quality Score",
            }
        )

        st.dataframe(
            top_companies,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ROE %": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "Revenue CAGR 5Y %": (
                    st.column_config.NumberColumn(
                        format="%.2f"
                    )
                ),
                "D/E": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "Quality Score": (
                    st.column_config.ProgressColumn(
                        min_value=0,
                        max_value=100,
                        format="%.2f",
                    )
                ),
            },
        )


show_home()