import re

def normalize_year(year):
    """
    Convert year formats like FY24, FY2024, 2024
    into integer year 2024.
    """

    year = str(year).strip().upper()

    year = year.replace("FY", "")

    if len(year) == 2:
        return int("20" + year)

    return int(year)


def normalize_ticker(ticker):
    """
    Convert ticker names into standard format.
    """

    ticker = str(ticker).strip().upper()

    ticker = ticker.replace(".NS", "")
    ticker = ticker.replace(".BO", "")

    return ticker