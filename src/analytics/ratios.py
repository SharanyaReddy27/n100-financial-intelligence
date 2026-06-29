def safe_divide(numerator, denominator):
    if denominator is None or denominator == 0:
        return None
    return numerator / denominator


def net_profit_margin(net_profit, sales):
    result = safe_divide(net_profit, sales)
    return None if result is None else result * 100


def operating_profit_margin(operating_profit, sales):
    result = safe_divide(operating_profit, sales)
    return None if result is None else result * 100


def opm_mismatch_flag(calculated_opm, source_opm):
    if calculated_opm is None or source_opm is None:
        return False
    return abs(calculated_opm - source_opm) > 1


def return_on_equity(net_profit, equity_capital, reserves):
    equity = equity_capital + reserves
    if equity <= 0:
        return None
    return (net_profit / equity) * 100


def return_on_capital_employed(operating_profit, depreciation, equity_capital, reserves, borrowings):
    ebit = operating_profit - depreciation
    capital_employed = equity_capital + reserves + borrowings
    if capital_employed <= 0:
        return None
    return (ebit / capital_employed) * 100


def return_on_assets(net_profit, total_assets):
    if total_assets == 0:
        return None
    return (net_profit / total_assets) * 100
def debt_to_equity(borrowings, equity_capital, reserves):
    if borrowings == 0:
        return 0

    equity = equity_capital + reserves

    if equity <= 0:
        return None

    return borrowings / equity


def high_leverage_flag(de_ratio, broad_sector):
    if de_ratio is None:
        return False

    if broad_sector == "Financials":
        return False

    return de_ratio > 5


def interest_coverage_ratio(operating_profit, other_income, interest):
    if interest == 0:
        return None

    return (operating_profit + other_income) / interest


def icr_label(icr):
    if icr is None:
        return "Debt Free"

    return ""


def icr_warning_flag(icr):
    if icr is None:
        return False

    return icr < 1.5


def net_debt(borrowings, investments):
    return borrowings - investments


def asset_turnover(sales, total_assets):
    if total_assets == 0:
        return None

    return sales / total_assets