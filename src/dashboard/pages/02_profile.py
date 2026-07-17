from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_ratios,
    get_pl,
    get_bs,
    get_cf,
    get_sectors,
    get_pros_cons,
)


def safe_value(value, suffix=""):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):,.2f}{suffix}"


def extract_year_number(series):
    return pd.to_numeric(
        series.astype(str).str.extract(r"(\d{4})")[0],
        errors="coerce",
    )


def get_latest_annual_row(df):
    if df.empty:
        return None

    data = df[
        df["year"].astype(str).str.upper() != "TTM"
    ].copy()

    data["year_num"] = extract_year_number(
        data["year"]
    )

    data = data.dropna(
        subset=["year_num"]
    )

    if data.empty:
        return None

    return (
        data.sort_values("year_num")
        .iloc[-1]
    )


def show_profile():
    st.title("Company Profile")

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

    company_data = companies.merge(
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

    company_data["search_label"] = (
        company_data["company_id"]
        + " — "
        + company_data["company_name"].fillna("")
    )

    search_text = st.text_input(
        "Search by company name or ticker",
        placeholder="Example: TCS, Reliance, HDFC Bank",
    ).strip()

    options = company_data["search_label"].tolist()

    if search_text:
        filtered_options = [
            option
            for option in options
            if search_text.lower() in option.lower()
        ]
    else:
        filtered_options = options

    if not filtered_options:
        st.warning(
            "Ticker not found — please try another."
        )
        return

    selected_label = st.selectbox(
        "Select company",
        filtered_options,
    )

    selected_ticker = selected_label.split(
        " — ",
        maxsplit=1,
    )[0]

    selected_company = company_data[
        company_data["company_id"] == selected_ticker
    ]

    if selected_company.empty:
        st.warning(
            "Ticker not found — please try another."
        )
        return

    company_row = selected_company.iloc[0]

    ratios = get_ratios(selected_ticker)
    pl = get_pl(selected_ticker)
    bs = get_bs(selected_ticker)
    cf = get_cf(selected_ticker)
    pros_cons = get_pros_cons(selected_ticker)

    latest_ratio = get_latest_annual_row(ratios)
    latest_cf = get_latest_annual_row(cf)

    company_name = company_row.get(
        "company_name",
        selected_ticker,
    )

    st.subheader(
        f"{company_name} ({selected_ticker})"
    )

    st.markdown(
        f"""
        **Sector:** {company_row.get("broad_sector", "N/A")}  
        **Sub-sector:** {company_row.get("sub_sector", "N/A")}  
        **NSE Ticker:** {selected_ticker}  
        **Website:** {company_row.get("website", "N/A")}
        """
    )

    about = company_row.get(
        "about_company",
        "",
    )

    if pd.notna(about) and str(about).strip():
        st.info(str(about))

    if latest_ratio is None:
        st.warning(
            "Financial ratio data is unavailable for this company."
        )
        return

    roce_value = company_row.get(
        "roce_percentage"
    )

    if pd.isna(roce_value):
        roce_value = None

    fcf_value = None

    if latest_cf is not None:
        operating_activity = latest_cf.get(
            "operating_activity"
        )
        investing_activity = latest_cf.get(
            "investing_activity"
        )

        if (
            pd.notna(operating_activity)
            and pd.notna(investing_activity)
        ):
            fcf_value = (
                operating_activity
                + investing_activity
            )

    kpi_row_1 = st.columns(3)

    kpi_row_1[0].metric(
        "ROE",
        safe_value(
            latest_ratio.get(
                "return_on_equity_pct"
            ),
            "%",
        ),
    )

    kpi_row_1[1].metric(
        "ROCE",
        safe_value(
            roce_value,
            "%",
        ),
    )

    kpi_row_1[2].metric(
        "Net Profit Margin",
        safe_value(
            latest_ratio.get(
                "net_profit_margin_pct"
            ),
            "%",
        ),
    )

    kpi_row_2 = st.columns(3)

    kpi_row_2[0].metric(
        "Debt to Equity",
        safe_value(
            latest_ratio.get(
                "debt_to_equity"
            )
        ),
    )

    kpi_row_2[1].metric(
        "Revenue CAGR 5Y",
        safe_value(
            latest_ratio.get(
                "revenue_cagr_5yr"
            ),
            "%",
        ),
    )

    kpi_row_2[2].metric(
        "Free Cash Flow",
        safe_value(
            fcf_value,
            " Cr",
        ),
    )

    st.divider()

    if not pl.empty:
        pl_chart_data = pl[
            pl["year"].astype(str).str.upper() != "TTM"
        ].copy()

        pl_chart_data["year_num"] = extract_year_number(
            pl_chart_data["year"]
        )

        pl_chart_data = (
            pl_chart_data
            .dropna(subset=["year_num"])
            .sort_values("year_num")
            .tail(10)
        )

        if not pl_chart_data.empty:
            st.subheader(
                "Revenue and Net Profit — Last 10 Years"
            )

            revenue_profit_chart = go.Figure()

            revenue_profit_chart.add_bar(
                x=pl_chart_data["year"],
                y=pl_chart_data["sales"],
                name="Revenue",
            )

            revenue_profit_chart.add_bar(
                x=pl_chart_data["year"],
                y=pl_chart_data["net_profit"],
                name="Net Profit",
            )

            revenue_profit_chart.update_layout(
                barmode="group",
                height=450,
                xaxis_title="Year",
                yaxis_title="₹ Crore",
                margin=dict(
                    l=20,
                    r=20,
                    t=40,
                    b=20,
                ),
            )

            st.plotly_chart(
                revenue_profit_chart,
                use_container_width=True,
            )

    if not ratios.empty:
        ratio_chart_data = ratios[
            ratios["year"].astype(str).str.upper() != "TTM"
        ].copy()

        ratio_chart_data["year_num"] = extract_year_number(
            ratio_chart_data["year"]
        )

        ratio_chart_data = (
            ratio_chart_data
            .dropna(subset=["year_num"])
            .sort_values("year_num")
            .tail(10)
        )

        if not ratio_chart_data.empty:
            ratio_chart_data[
                "roce_percentage"
            ] = roce_value

            st.subheader(
                "ROE and ROCE Trend"
            )

            roe_roce_chart = go.Figure()

            roe_roce_chart.add_trace(
                go.Scatter(
                    x=ratio_chart_data["year"],
                    y=ratio_chart_data[
                        "return_on_equity_pct"
                    ],
                    mode="lines+markers",
                    name="ROE",
                    yaxis="y1",
                )
            )

            roe_roce_chart.add_trace(
                go.Scatter(
                    x=ratio_chart_data["year"],
                    y=ratio_chart_data[
                        "roce_percentage"
                    ],
                    mode="lines+markers",
                    name="ROCE",
                    yaxis="y2",
                )
            )

            roe_roce_chart.update_layout(
                height=450,
                xaxis_title="Year",
                yaxis=dict(
                    title="ROE %",
                    side="left",
                ),
                yaxis2=dict(
                    title="ROCE %",
                    overlaying="y",
                    side="right",
                ),
                margin=dict(
                    l=20,
                    r=20,
                    t=40,
                    b=20,
                ),
            )

            st.plotly_chart(
                roe_roce_chart,
                use_container_width=True,
            )

    st.divider()

    st.subheader("Pros and Cons")

    if pros_cons.empty:
        st.info(
            "No pros and cons are available for this company."
        )
    else:
        pros_column, cons_column = st.columns(2)

        with pros_column:
            st.markdown("### ✅ Pros")

            valid_pros = (
                pros_cons["pros"]
                .dropna()
                .astype(str)
                .str.strip()
            )

            if valid_pros.empty:
                st.write("No pros available.")
            else:
                for item in valid_pros:
                    st.success(item)

        with cons_column:
            st.markdown("### ❌ Cons")

            valid_cons = (
                pros_cons["cons"]
                .dropna()
                .astype(str)
                .str.strip()
            )

            if valid_cons.empty:
                st.write("No cons available.")
            else:
                for item in valid_cons:
                    st.error(item)


show_profile()