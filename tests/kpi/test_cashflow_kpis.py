import sys
import os

sys.path.append(os.path.abspath("."))

from src.analytics.cashflow_kpis import (
    free_cash_flow,
    cfo_quality_ratio,
    cfo_quality_label,
    capex_intensity,
    capex_label,
    fcf_conversion_rate,
    capital_allocation_pattern,
)


def test_free_cash_flow():
    assert free_cash_flow(100, -30) == 70


def test_cfo_quality_ratio():
    assert cfo_quality_ratio(120, 100) == 1.2


def test_cfo_quality_zero_pat():
    assert cfo_quality_ratio(100, 0) is None


def test_cfo_quality_label_high():
    assert cfo_quality_label(1.2) == "High Quality"


def test_cfo_quality_label_moderate():
    assert cfo_quality_label(0.7) == "Moderate"


def test_cfo_quality_label_low():
    assert cfo_quality_label(0.2) == "Accrual Risk"


def test_capex_intensity():
    assert round(capex_intensity(-50, 1000), 2) == 5.00


def test_capex_label_asset_light():
    assert capex_label(2.5) == "Asset Light"


def test_capex_label_moderate():
    assert capex_label(5.5) == "Moderate"


def test_capex_label_capital_intensive():
    assert capex_label(10) == "Capital Intensive"


def test_fcf_conversion():
    assert fcf_conversion_rate(100, 200) == 50


def test_fcf_conversion_zero():
    assert fcf_conversion_rate(100, 0) is None


def test_pattern_reinvestor():
    assert capital_allocation_pattern(100, -50, -20) == "Reinvestor"


def test_pattern_growth():
    assert capital_allocation_pattern(-100, -50, 20) == "Growth Funded by Debt"


def test_pattern_cash_accumulator():
    assert capital_allocation_pattern(100, 50, 20) == "Cash Accumulator"


def test_pattern_distress():
    assert capital_allocation_pattern(-100, 50, 20) == "Distress Signal"