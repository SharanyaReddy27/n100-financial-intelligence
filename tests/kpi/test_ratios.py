import sys
import os

sys.path.append(os.path.abspath("."))

from src.analytics.ratios import (
    net_profit_margin,
    operating_profit_margin,
    opm_mismatch_flag,
    return_on_equity,
    return_on_capital_employed,
    return_on_assets,
)


def test_net_profit_margin_normal():
    assert net_profit_margin(100, 1000) == 10


def test_net_profit_margin_zero_sales():
    assert net_profit_margin(100, 0) is None


def test_operating_profit_margin_normal():
    assert operating_profit_margin(200, 1000) == 20


def test_opm_mismatch_true():
    assert opm_mismatch_flag(20, 18) is True


def test_opm_mismatch_false():
    assert opm_mismatch_flag(20, 19.5) is False


def test_return_on_equity_normal():
    assert round(return_on_equity(100, 200, 300), 2) == 20.00


def test_return_on_equity_negative_equity():
    assert return_on_equity(100, -200, 100) is None


def test_return_on_assets_zero_assets():
    assert return_on_assets(100, 0) is None