from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from src.screener.engine import (
    add_composite_quality_score,
    add_scoring_inputs,
    apply_filters,
    load_financial_data,
)


PRESETS = {
    "Quality": {
        "roe_min": 15.0,
        "debt_to_equity_max": 1.0,
        "free_cash_flow_min": 0.0,
        "revenue_cagr_5yr_min": 10.0,
    },
    "Value": {
        "pe_ratio_max": 20.0,
        "pb_ratio_max": 3.0,
        "debt_to_equity_max": 2.0,
        "dividend_yield_min": 1.0,
    },
    "Growth": {
        "pat_cagr_5yr_min": 20.0,
        "revenue_cagr_5yr_min": 15.0,
        "debt_to_equity_max": 2.0,
    },
    "Dividend": {
        "dividend_yield_min": 2.0,
        "dividend_payout_max": 80.0,
        "free_cash_flow_min": 0.0,
    },
    "Debt-Free": {
        "debt_to_equity_equal": 0.0,
        "roe_min": 12.0,
        "sales_min": 5000.0,
    },
    "Turnaround": {
        "revenue_cagr_3yr_min": 10.0,
        "free_cash_flow_min": 0.0,
        "debt_to_equity_declining": True,
    },
}


DEFAULTS = {
    "roe_min": 0.0,
    "debt_to_equity_max": 10.0,
    "free_cash_flow_min": -100000.0,
    "revenue_cagr_5yr_min": -100.0,
    "pat_cagr_5yr_min": -100.0,
    "opm_min": -100.0,
    "pe_ratio_max": 500.0,
    "pb_ratio_max": 100.0,
    "dividend_yield_min": 0.0,
    "icr_min": -100.0,
}


def initialise_state():
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_preset(preset_name):
    for key, value in DEFAULTS.items():
        st.session_state[key] = value

    for key, value in PRESETS[preset_name].items():
        if key in st.session_state:
            st.session_state[key] = value


def build_filters():
    return {
        "roe_min": st.session_state.roe_min,
        "debt_to_equity_max": st.session_state.debt_to_equity_max,
        "free_cash_flow_min": st.session_state.free_cash_flow_min,
        "revenue_cagr_5yr_min": st.session_state.revenue_cagr_5yr_min,
        "pat_cagr_5yr_min": st.session_state.pat_cagr_5yr_min,
        "opm_min": st.session_state.opm_min,
        "pe_ratio_max": st.session_state.pe_ratio_max,
        "pb_ratio_max": st.session_state.pb_ratio_max,
        "dividend_yield_min": st.session_state.dividend_yield_min,
        "icr_min": st.session_state.icr_min,
    }


def show_screener():
    st.title("Financial Screener")

    st.caption(
        "Filter Nifty 100 companies using financial thresholds "
        "or apply a predefined screening strategy."
    )

    initialise_state()

    st.sidebar.subheader("Preset Screeners")

    preset_columns = st.sidebar.columns(2)

    preset_names = list(PRESETS.keys())

    for index, preset_name in enumerate(preset_names):
        column = preset_columns[index % 2]

        if column.button(
            preset_name,
            use_container_width=True,
            key=f"preset_{preset_name}",
        ):
            apply_preset(preset_name)
            st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Custom Filters")

    st.sidebar.slider(
        "Minimum ROE (%)",
        min_value=-50.0,
        max_value=100.0,
        step=1.0,
        key="roe_min",
    )

    st.sidebar.slider(
        "Maximum Debt-to-Equity",
        min_value=0.0,
        max_value=20.0,
        step=0.1,
        key="debt_to_equity_max",
    )

    st.sidebar.slider(
        "Minimum Free Cash Flow (₹ Cr)",
        min_value=-100000.0,
        max_value=100000.0,
        step=500.0,
        key="free_cash_flow_min",
    )

    st.sidebar.slider(
        "Minimum Revenue CAGR 5Y (%)",
        min_value=-100.0,
        max_value=100.0,
        step=1.0,
        key="revenue_cagr_5yr_min",
    )

    st.sidebar.slider(
        "Minimum PAT CAGR 5Y (%)",
        min_value=-100.0,
        max_value=100.0,
        step=1.0,
        key="pat_cagr_5yr_min",
    )

    st.sidebar.slider(
        "Minimum OPM (%)",
        min_value=-100.0,
        max_value=100.0,
        step=1.0,
        key="opm_min",
    )

    st.sidebar.slider(
        "Maximum P/E",
        min_value=0.0,
        max_value=500.0,
        step=1.0,
        key="pe_ratio_max",
    )

    st.sidebar.slider(
        "Maximum P/B",
        min_value=0.0,
        max_value=100.0,
        step=0.5,
        key="pb_ratio_max",
    )

    st.sidebar.slider(
        "Minimum Dividend Yield (%)",
        min_value=0.0,
        max_value=20.0,
        step=0.1,
        key="dividend_yield_min",
    )

    st.sidebar.slider(
        "Minimum Interest Coverage",
        min_value=-100.0,
        max_value=100.0,
        step=0.5,
        key="icr_min",
    )

    try:
        data = load_financial_data()
        data = add_scoring_inputs(data)
        data = add_composite_quality_score(data)
    except Exception as error:
        st.error(f"Unable to load screener data: {error}")
        return

    filters = build_filters()

    filtered = apply_filters(
        data,
        filters,
    )

    visible_columns = [
        "company_id",
        "broad_sector",
        "composite_quality_score",
        "return_on_equity_pct",
        "debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "operating_profit_margin_pct",
        "pe_ratio",
        "pb_ratio",
        "dividend_yield_pct",
        "interest_coverage",
    ]

    visible_columns = [
        column
        for column in visible_columns
        if column in filtered.columns
    ]

    result = filtered[visible_columns].copy()

    result = result.rename(
        columns={
            "company_id": "Ticker",
            "broad_sector": "Sector",
            "composite_quality_score": "Composite Score",
            "return_on_equity_pct": "ROE %",
            "debt_to_equity": "D/E",
            "free_cash_flow_cr": "FCF ₹ Cr",
            "revenue_cagr_5yr": "Revenue CAGR 5Y %",
            "pat_cagr_5yr": "PAT CAGR 5Y %",
            "operating_profit_margin_pct": "OPM %",
            "pe_ratio": "P/E",
            "pb_ratio": "P/B",
            "dividend_yield_pct": "Dividend Yield %",
            "interest_coverage": "ICR",
        }
    )

    st.subheader(
        f"{len(result)} companies match your filters"
    )

    if result.empty:
        st.info(
            "No companies match the current filters. "
            "Try relaxing one or more thresholds."
        )
        return

    st.dataframe(
        result,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Composite Score": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.2f",
            ),
            "ROE %": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "D/E": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "FCF ₹ Cr": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "Revenue CAGR 5Y %": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "PAT CAGR 5Y %": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "OPM %": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "P/E": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "P/B": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "Dividend Yield %": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "ICR": st.column_config.NumberColumn(
                format="%.2f"
            ),
        },
    )

    csv_data = result.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Download results as CSV",
        data=csv_data,
        file_name="screener_results.csv",
        mime="text/csv",
        use_container_width=True,
    )


show_screener()