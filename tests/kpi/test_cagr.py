import sys
import os

sys.path.append(os.path.abspath("."))

from src.analytics.cagr import calculate_cagr


def test_cagr_normal():
    value, flag = calculate_cagr(100, 200, 5)
    assert round(value, 2) == 14.87
    assert flag == "NORMAL"


def test_cagr_zero_base():
    value, flag = calculate_cagr(0, 200, 5)
    assert value is None
    assert flag == "ZERO_BASE"


def test_cagr_decline_to_loss():
    value, flag = calculate_cagr(100, -50, 5)
    assert value is None
    assert flag == "DECLINE_TO_LOSS"


def test_cagr_turnaround():
    value, flag = calculate_cagr(-100, 50, 5)
    assert value is None
    assert flag == "TURNAROUND"


def test_cagr_both_negative():
    value, flag = calculate_cagr(-100, -50, 5)
    assert value is None
    assert flag == "BOTH_NEGATIVE"


def test_cagr_insufficient_years():
    value, flag = calculate_cagr(100, 200, 0)
    assert value is None
    assert flag == "INSUFFICIENT"


def test_cagr_missing_start():
    value, flag = calculate_cagr(None, 200, 5)
    assert value is None
    assert flag == "INSUFFICIENT"


def test_cagr_missing_end():
    value, flag = calculate_cagr(100, None, 5)
    assert value is None
    assert flag == "INSUFFICIENT"


def test_cagr_one_year():
    value, flag = calculate_cagr(100, 110, 1)
    assert round(value, 2) == 10.00
    assert flag == "NORMAL"


def test_cagr_negative_zero_case():
    value, flag = calculate_cagr(-100, 0, 5)
    assert value is None
    assert flag == "UNKNOWN"