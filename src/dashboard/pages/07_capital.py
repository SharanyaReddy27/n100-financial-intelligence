from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st


CAPITAL_FILE = Path("output/capital_allocation.csv")
COMPANIES_FILE = Path("data/processed/companies.csv")
SECTORS_FILE = Path("data/processed/sectors.csv")


def clean_company_id(df):
    df = df.copy()

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


@st.cache_data(ttl=600)
def load_capital_allocation_data():
    if not CAPITAL_FILE.exists():
        raise FileNotFoundError(
            "output/capital_allocation.csv was not found."
        )

    capital = pd.read_csv(CAPITAL_FILE)
    companies = pd.read_csv(COMPANIES_FILE)
    sectors = pd.read_csv(SECTORS_FILE)

    capital = clean_company_id(capital)

    companies = companies.rename(
        columns={"id": "company_id"}
    )
    companies = clean_company_id(companies)

    sectors = clean_company_id(sectors)

    capital = capital[
        capital["year"].astype(str).str.upper() != "TTM"
    ].copy()

    capital["year_num"] = extract_year_number(
        capital["year"]
    )

    latest_capital = (
        capital
        .dropna(subset=["year_num"])
        .sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )

    data = latest_capital.merge(
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

    return data


def show_capital_allocation():
    st.title("Capital Allocation Map")

    st.caption(
        "Explore the latest capital allocation pattern "
        "for Nifty 100 companies."
    )

    try:
        data = load_capital_allocation_data()
    except Exception as error:
        st.error(
            f"Unable to load capital allocation data: {error}"
        )
        return

    if data.empty:
        st.warning(
            "Capital allocation data is unavailable."
        )
        return

    pattern_summary = (
        data.groupby("pattern_label")
        .agg(
            company_count=("company_id", "nunique"),
        )
        .reset_index()
        .sort_values(
            "company_count",
            ascending=False,
        )
    )

    st.subheader("Capital Allocation Patterns")

    treemap = px.treemap(
        pattern_summary,
        path=["pattern_label"],
        values="company_count",
        title=(
            "Nifty 100 Companies by Capital Allocation Pattern"
        ),
        hover_data={
            "company_count": True,
        },
    )

    treemap.update_traces(
        textinfo="label+value+percent root"
    )

    treemap.update_layout(
        height=550,
        margin=dict(
            l=10,
            r=10,
            t=60,
            b=10,
        ),
    )

    event = st.plotly_chart(
        treemap,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="capital_treemap",
    )

    pattern_options = sorted(
        data["pattern_label"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_pattern = st.selectbox(
        "Select a pattern to view companies",
        options=pattern_options,
    )

    try:
        selected_points = event.selection.points

        if selected_points:
            clicked_label = selected_points[0].get(
                "label"
            )

            if clicked_label in pattern_options:
                selected_pattern = clicked_label
    except Exception:
        pass

    selected_data = data[
        data["pattern_label"] == selected_pattern
    ].copy()

    st.subheader(
        f"{selected_pattern} Companies"
    )

    st.write(
        f"{selected_data['company_id'].nunique()} "
        "companies follow this pattern."
    )

    table_columns = [
        "company_id",
        "company_name",
        "broad_sector",
        "sub_sector",
        "year",
        "cfo_sign",
        "cfi_sign",
        "cff_sign",
        "pattern_label",
    ]

    available_columns = [
        column
        for column in table_columns
        if column in selected_data.columns
    ]

    company_table = selected_data[
        available_columns
    ].copy()

    company_table = company_table.rename(
        columns={
            "company_id": "Ticker",
            "company_name": "Company",
            "broad_sector": "Sector",
            "sub_sector": "Sub-sector",
            "year": "Year",
            "cfo_sign": "CFO Sign",
            "cfi_sign": "CFI Sign",
            "cff_sign": "CFF Sign",
            "pattern_label": "Pattern",
        }
    )

    st.dataframe(
        company_table,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Pattern Distribution")

    distribution_chart = px.bar(
        pattern_summary,
        x="pattern_label",
        y="company_count",
        text="company_count",
        labels={
            "pattern_label": "Pattern",
            "company_count": "Company Count",
        },
    )

    distribution_chart.update_traces(
        textposition="outside"
    )

    distribution_chart.update_layout(
        height=450,
        xaxis_title="",
        yaxis_title="Companies",
        margin=dict(
            l=20,
            r=20,
            t=30,
            b=100,
        ),
    )

    st.plotly_chart(
        distribution_chart,
        use_container_width=True,
    )


show_capital_allocation()