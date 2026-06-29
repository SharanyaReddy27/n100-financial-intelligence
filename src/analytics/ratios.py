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