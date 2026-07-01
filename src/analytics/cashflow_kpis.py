def free_cash_flow(operating_activity, investing_activity):
    return operating_activity + investing_activity


def cfo_quality_ratio(cfo, pat):
    if pat == 0:
        return None
    return cfo / pat


def cfo_quality_label(ratio):
    if ratio is None:
        return "Not Available"
    if ratio > 1.0:
        return "High Quality"
    if ratio >= 0.5:
        return "Moderate"
    return "Accrual Risk"


def capex_intensity(investing_activity, sales):
    if sales == 0:
        return None
    return abs(investing_activity) / sales * 100


def capex_label(value):
    if value is None:
        return "Not Available"
    if value < 3:
        return "Asset Light"
    if value <= 8:
        return "Moderate"
    return "Capital Intensive"


def fcf_conversion_rate(fcf, operating_profit):
    if operating_profit == 0:
        return None
    return fcf / operating_profit * 100


def sign_value(value):
    if value > 0:
        return "+"
    if value < 0:
        return "-"
    return "0"


def capital_allocation_pattern(cfo, cfi, cff):
    pattern = (sign_value(cfo), sign_value(cfi), sign_value(cff))

    if pattern == ("+", "-", "-"):
        return "Reinvestor"
    if pattern == ("+", "+", "-"):
        return "Liquidating Assets"
    if pattern == ("-", "+", "+"):
        return "Distress Signal"
    if pattern == ("-", "-", "+"):
        return "Growth Funded by Debt"
    if pattern == ("+", "+", "+"):
        return "Cash Accumulator"
    if pattern == ("-", "-", "-"):
        return "Pre-Revenue"
    if pattern == ("+", "-", "+"):
        return "Mixed"

    return "Other"