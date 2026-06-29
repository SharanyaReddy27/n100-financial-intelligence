import sys
import os

sys.path.append(os.path.abspath("."))

from src.analytics.ratios import (
    debt_to_equity,
    high_leverage_flag,
    interest_coverage_ratio,
    icr_label,
    icr_warning_flag,
    net_debt,
    asset_turnover,
)


def test_debt_to_equity_normal():
    assert debt_to_equity(100, 200, 300) == 0.2


def test_debt_to_equity_debt_free():
    assert debt_to_equity(0, 200, 300) == 0


def test_debt_to_equity_negative_equity():
    assert debt_to_equity(100, -300, 100) is None


def test_high_leverage_non_financial():
    assert high_leverage_flag(6, "Industrials") is True


def test_high_leverage_financial_suppressed():
    assert high_leverage_flag(6, "Financials") is False


def test_interest_coverage_normal():
    assert interest_coverage_ratio(100, 50, 10) == 15


def test_interest_coverage_zero_interest():
    assert interest_coverage_ratio(100, 50, 0) is None


def test_icr_label_debt_free():
    assert icr_label(None) == "Debt Free"


def test_icr_warning_true():
    assert icr_warning_flag(1.2) is True


def test_icr_warning_false():
    assert icr_warning_flag(3.0) is False


def test_net_debt():
    assert net_debt(500, 200) == 300


def test_asset_turnover_normal():
    assert asset_turnover(1000, 500) == 2


def test_asset_turnover_zero_assets():
    assert asset_turnover(1000, 0) is None