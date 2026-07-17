from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st


DB_PATH = Path("db/nifty100.db")


def get_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at: {DB_PATH.resolve()}"
        )

    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=600)
def get_companies():
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT
                id AS company_id,
                company_name,
                company_logo,
                about_company,
                website,
                nse_profile,
                bse_profile,
                face_value,
                book_value,
                roce_percentage,
                roe_percentage
            FROM companies
            ORDER BY company_name
            """,
            conn,
        )


@st.cache_data(ttl=600)
def get_ratios(ticker=None, year=None):
    query = """
        SELECT *
        FROM financial_ratios
        WHERE 1 = 1
    """
    params = []

    if ticker:
        query += " AND UPPER(company_id) = UPPER(?)"
        params.append(ticker)

    if year:
        query += " AND year = ?"
        params.append(year)

    query += " ORDER BY company_id, year"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=600)
def get_pl(ticker):
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT *
            FROM profitandloss
            WHERE UPPER(company_id) = UPPER(?)
            ORDER BY year
            """,
            conn,
            params=[ticker],
        )


@st.cache_data(ttl=600)
def get_bs(ticker):
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT *
            FROM balancesheet
            WHERE UPPER(company_id) = UPPER(?)
            ORDER BY year
            """,
            conn,
            params=[ticker],
        )


@st.cache_data(ttl=600)
def get_cf(ticker):
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT *
            FROM cashflow
            WHERE UPPER(company_id) = UPPER(?)
            ORDER BY year
            """,
            conn,
            params=[ticker],
        )


@st.cache_data(ttl=600)
def get_sectors():
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT
                company_id,
                broad_sector,
                sub_sector,
                index_weight_pct,
                market_cap_category
            FROM sectors
            ORDER BY broad_sector, company_id
            """,
            conn,
        )


@st.cache_data(ttl=600)
def get_peers(group_name=None):
    query = """
        SELECT
            company_id,
            peer_group_name,
            is_benchmark
        FROM peer_groups
    """
    params = []

    if group_name:
        query += " WHERE peer_group_name = ?"
        params.append(group_name)

    query += " ORDER BY peer_group_name, company_id"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=600)
def get_market_cap(ticker=None, year=None):
    query = """
        SELECT *
        FROM market_cap
        WHERE 1 = 1
    """
    params = []

    if ticker:
        query += " AND UPPER(company_id) = UPPER(?)"
        params.append(ticker)

    if year:
        query += " AND year = ?"
        params.append(year)

    query += " ORDER BY company_id, year"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=600)
def get_pros_cons(ticker):
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT pros, cons
            FROM prosandcons
            WHERE UPPER(company_id) = UPPER(?)
            """,
            conn,
            params=[ticker],
        )


@st.cache_data(ttl=600)
def get_valuation(ticker):
    try:
        with get_connection() as conn:
            return pd.read_sql_query(
                """
                SELECT *
                FROM valuation
                WHERE UPPER(company_id) = UPPER(?)
                """,
                conn,
                params=[ticker],
            )
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600)
def get_home_data(year=2024):
    with get_connection() as conn:
        ratios = pd.read_sql_query(
            """
            SELECT *
            FROM financial_ratios
            WHERE year LIKE ?
            """,
            conn,
            params=[f"%{year}%"],
        )

        market_cap = pd.read_sql_query(
            """
            SELECT *
            FROM market_cap
            WHERE year = ?
            """,
            conn,
            params=[year],
        )

        sectors = pd.read_sql_query(
            """
            SELECT company_id, broad_sector, sub_sector
            FROM sectors
            """,
            conn,
        )

        companies = pd.read_sql_query(
            """
            SELECT id AS company_id, company_name
            FROM companies
            """,
            conn,
        )

    return ratios, market_cap, sectors, companies