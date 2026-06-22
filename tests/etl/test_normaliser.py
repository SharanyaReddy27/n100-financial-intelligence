import sys
import os

sys.path.append(os.path.abspath("."))

from src.etl.normaliser import normalize_year, normalize_ticker


def test_normalize_year_fy24():
    assert normalize_year("FY24") == 2024

def test_normalize_year_fy2024():
    assert normalize_year("FY2024") == 2024

def test_normalize_year_2024():
    assert normalize_year("2024") == 2024

def test_normalize_year_spaces():
    assert normalize_year(" 2023 ") == 2023

def test_normalize_year_fy23():
    assert normalize_year("FY23") == 2023

def test_normalize_year_fy22():
    assert normalize_year("FY22") == 2022

def test_normalize_year_fy21():
    assert normalize_year("FY21") == 2021

def test_normalize_year_fy20():
    assert normalize_year("FY20") == 2020

def test_normalize_year_fy19():
    assert normalize_year("FY19") == 2019

def test_normalize_year_fy18():
    assert normalize_year("FY18") == 2018

def test_normalize_year_string_number():
    assert normalize_year("2022") == 2022

def test_normalize_year_lowercase_fy():
    assert normalize_year("fy24") == 2024

def test_normalize_year_mixedcase_fy():
    assert normalize_year("Fy24") == 2024

def test_normalize_year_with_space_fy():
    assert normalize_year(" FY24 ") == 2024

def test_normalize_year_2020():
    assert normalize_year("2020") == 2020

def test_normalize_year_2021():
    assert normalize_year("2021") == 2021

def test_normalize_year_2022():
    assert normalize_year("2022") == 2022

def test_normalize_year_2023():
    assert normalize_year("2023") == 2023

def test_normalize_year_2025():
    assert normalize_year("2025") == 2025

def test_normalize_year_2026():
    assert normalize_year("2026") == 2026


def test_normalize_ticker_reliance_ns():
    assert normalize_ticker("reliance.ns") == "RELIANCE"

def test_normalize_ticker_tcs_spaces():
    assert normalize_ticker(" tcs ") == "TCS"

def test_normalize_ticker_infosys():
    assert normalize_ticker("infy") == "INFY"

def test_normalize_ticker_upper():
    assert normalize_ticker("HDFCBANK") == "HDFCBANK"

def test_normalize_ticker_lower():
    assert normalize_ticker("hdfcbank") == "HDFCBANK"

def test_normalize_ticker_mixed():
    assert normalize_ticker("Reliance") == "RELIANCE"

def test_normalize_ticker_bo():
    assert normalize_ticker("wipro.bo") == "WIPRO"

def test_normalize_ticker_ns_upper():
    assert normalize_ticker("TCS.NS") == "TCS"

def test_normalize_ticker_bo_upper():
    assert normalize_ticker("TCS.BO") == "TCS"

def test_normalize_ticker_spaces_ns():
    assert normalize_ticker(" reliance.ns ") == "RELIANCE"

def test_normalize_ticker_axisbank():
    assert normalize_ticker("axisbank") == "AXISBANK"

def test_normalize_ticker_icicibank():
    assert normalize_ticker("icicibank") == "ICICIBANK"

def test_normalize_ticker_sbilife():
    assert normalize_ticker("sbilife") == "SBILIFE"

def test_normalize_ticker_abb():
    assert normalize_ticker("abb") == "ABB"

def test_normalize_ticker_zomato():
    assert normalize_ticker("zomato") == "ZOMATO"