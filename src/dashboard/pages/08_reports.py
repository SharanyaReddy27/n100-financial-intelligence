from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st


DB_PATH = "db/nifty100.db"


@st.cache_data(ttl=600)
def load_reports():
    with sqlite3.connect(DB_PATH) as conn:
        reports = pd.read_sql_query(
            """
            SELECT
                company_id,
                Year,
                Annual_Report
            FROM documents
            """,
            conn,
        )

        companies = pd.read_sql_query(
            """
            SELECT
                id AS company_id,
                company_name
            FROM companies
            """,
            conn,
        )

    reports["company_id"] = (
        reports["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    companies["company_id"] = (
        companies["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    reports["Year"] = pd.to_numeric(
        reports["Year"],
        errors="coerce",
    )

    reports = reports.merge(
        companies,
        on="company_id",
        how="left",
    )

    return reports


def show_reports():
    st.title("Annual Reports")

    st.caption(
        "Browse available annual reports for Nifty 100 companies."
    )

    try:
        reports = load_reports()
    except Exception as error:
        st.error(f"Unable to load reports: {error}")
        return

    if reports.empty:
        st.warning("No annual reports are available.")
        return

    reports["search_label"] = (
        reports["company_id"]
        + " — "
        + reports["company_name"].fillna("")
    )

    company_options = sorted(
        reports["search_label"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_company = st.selectbox(
        "Select Company",
        options=company_options,
    )

    ticker = selected_company.split(
        " — ",
        maxsplit=1,
    )[0]

    company_reports = reports[
        reports["company_id"] == ticker
    ].copy()

    company_reports = company_reports.sort_values(
        "Year",
        ascending=False,
        na_position="last",
    )

    st.subheader(ticker)

    if company_reports.empty:
        st.info(
            "No annual reports are available for this company."
        )
        return

    for _, row in company_reports.iterrows():
        year = row.get("Year")
        url = row.get("Annual_Report")

        year_text = (
            str(int(year))
            if pd.notna(year)
            else "Unknown Year"
        )

        left, right = st.columns([1, 3])

        with left:
            st.markdown(f"### {year_text}")

        with right:
            if pd.isna(url) or not str(url).strip():
                st.error("Report unavailable")
            else:
                st.link_button(
                    f"Open {year_text} Report",
                    str(url).strip(),
                    use_container_width=True,
                )


show_reports()