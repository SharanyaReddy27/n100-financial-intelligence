def calculate_cagr(start_value, end_value, years):
    """
    CAGR formula with edge case flags.
    Returns: (cagr_value, flag)
    """

    if years <= 0:
        return None, "INSUFFICIENT"

    if start_value is None or end_value is None:
        return None, "INSUFFICIENT"

    if start_value == 0:
        return None, "ZERO_BASE"

    if start_value > 0 and end_value > 0:
        cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
        return cagr, "NORMAL"

    if start_value > 0 and end_value < 0:
        return None, "DECLINE_TO_LOSS"

    if start_value < 0 and end_value > 0:
        return None, "TURNAROUND"

    if start_value < 0 and end_value < 0:
        return None, "BOTH_NEGATIVE"

    return None, "UNKNOWN"


def get_cagr_for_window(df, company_id, value_col, window):
    company_df = df[df["company_id"] == company_id].copy()

    company_df = company_df.sort_values("year_num")

    if len(company_df) < window + 1:
        return None, "INSUFFICIENT"

    start_value = company_df.iloc[-(window + 1)][value_col]
    end_value = company_df.iloc[-1][value_col]

    return calculate_cagr(start_value, end_value, window)