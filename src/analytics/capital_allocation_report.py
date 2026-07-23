from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "output"

CAPITAL_ALLOCATION_FILE = OUTPUT_DIR / "capital_allocation.csv"
CASHFLOW_INTELLIGENCE_FILE = OUTPUT_DIR / "cashflow_intelligence.xlsx"

PATTERN_CHANGES_FILE = OUTPUT_DIR / "pattern_changes.csv"
PATTERN_DISTRIBUTION_FILE = OUTPUT_DIR / "capital_allocation_distribution.csv"


# ============================================================
# HELPERS
# ============================================================

def normalize_company_id(value: Any) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def extract_year(value: Any) -> float:
    if pd.isna(value):
        return np.nan

    text = str(value).strip()

    try:
        numeric = float(text)

        if 1900 <= numeric <= 2100:
            return numeric
    except ValueError:
        pass

    import re

    match = re.search(r"(19|20)\d{2}", text)

    if match:
        return float(match.group())

    match = re.search(r"(?<!\d)(\d{2})(?!\d)", text)

    if match:
        year = int(match.group(1))

        if year <= 50:
            return float(2000 + year)

        return float(1900 + year)

    return np.nan


def detect_column(
    dataframe: pd.DataFrame,
    candidates: list[str],
    purpose: str,
) -> str:
    for column in candidates:
        if column in dataframe.columns:
            return column

    raise ValueError(
        f"Could not find {purpose} column. "
        f"Checked: {', '.join(candidates)}. "
        f"Available columns: {', '.join(dataframe.columns)}"
    )


# ============================================================
# LOAD AND PREPARE DATA
# ============================================================

def load_capital_allocation() -> tuple[pd.DataFrame, str]:
    if not CAPITAL_ALLOCATION_FILE.exists():
        raise FileNotFoundError(
            f"File not found: {CAPITAL_ALLOCATION_FILE}"
        )

    dataframe = pd.read_csv(CAPITAL_ALLOCATION_FILE)

    company_column = detect_column(
        dataframe,
        ["company_id", "ticker", "symbol"],
        "company identifier",
    )

    year_column = detect_column(
        dataframe,
        ["year", "financial_year", "fiscal_year"],
        "year",
    )

    pattern_column = detect_column(
        dataframe,
        [
            "capital_allocation_label",
            "capital_allocation_pattern",
            "allocation_pattern",
            "pattern_label",
            "pattern",
        ],
        "capital allocation pattern",
    )

    dataframe = dataframe.rename(
        columns={
            company_column: "company_id",
            year_column: "year",
            pattern_column: "capital_allocation_pattern",
        }
    )

    dataframe["company_id"] = (
        dataframe["company_id"].apply(normalize_company_id)
    )

    dataframe["_year_number"] = (
        dataframe["year"].apply(extract_year)
    )

    dataframe["capital_allocation_pattern"] = (
        dataframe["capital_allocation_pattern"]
        .fillna("Unavailable")
        .astype(str)
        .str.strip()
    )

    dataframe = dataframe[
        dataframe["company_id"] != ""
    ].copy()

    return dataframe, pattern_column


# ============================================================
# VALIDATION
# ============================================================

def validate_coverage(dataframe: pd.DataFrame) -> None:
    company_count = dataframe["company_id"].nunique()

    if company_count != 92:
        print(
            f"Warning: expected 92 companies, "
            f"but found {company_count}."
        )

    duplicate_count = dataframe.duplicated(
        subset=["company_id", "_year_number"]
    ).sum()

    if duplicate_count > 0:
        print(
            f"Warning: found {duplicate_count} duplicate "
            "company-year rows."
        )

    missing_years = dataframe["_year_number"].isna().sum()

    if missing_years > 0:
        print(
            f"Warning: {missing_years} rows have an "
            "unrecognized year value."
        )


# ============================================================
# LATEST-YEAR DISTRIBUTION
# ============================================================

def build_latest_distribution(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    valid_data = dataframe.dropna(
        subset=["_year_number"]
    ).copy()

    valid_data = valid_data.sort_values(
        ["company_id", "_year_number"]
    )

    latest_rows = valid_data.groupby(
        "company_id",
        as_index=False,
    ).tail(1)

    distribution = (
        latest_rows["capital_allocation_pattern"]
        .value_counts()
        .rename_axis("capital_allocation_pattern")
        .reset_index(name="company_count")
    )

    distribution["percentage"] = (
        distribution["company_count"]
        / len(latest_rows)
        * 100
    ).round(2)

    distribution = distribution.sort_values(
        ["company_count", "capital_allocation_pattern"],
        ascending=[False, True],
    ).reset_index(drop=True)

    return distribution


# ============================================================
# PATTERN CHANGES
# ============================================================

def build_pattern_changes(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    valid_data = dataframe.dropna(
        subset=["_year_number"]
    ).copy()

    valid_data = valid_data.sort_values(
        ["company_id", "_year_number"]
    )

    change_records = []

    for company_id, company_data in valid_data.groupby(
        "company_id"
    ):
        company_data = company_data.drop_duplicates(
            subset=["_year_number"],
            keep="last",
        )

        if len(company_data) < 2:
            continue

        previous_row = company_data.iloc[-2]
        latest_row = company_data.iloc[-1]

        previous_pattern = str(
            previous_row["capital_allocation_pattern"]
        ).strip()

        latest_pattern = str(
            latest_row["capital_allocation_pattern"]
        ).strip()

        if previous_pattern != latest_pattern:
            change_records.append(
                {
                    "company_id": company_id,
                    "previous_year": int(
                        previous_row["_year_number"]
                    ),
                    "latest_year": int(
                        latest_row["_year_number"]
                    ),
                    "previous_pattern": previous_pattern,
                    "latest_pattern": latest_pattern,
                    "change_description": (
                        f"Moved from {previous_pattern} "
                        f"to {latest_pattern}"
                    ),
                }
            )

    return pd.DataFrame(
        change_records,
        columns=[
            "company_id",
            "previous_year",
            "latest_year",
            "previous_pattern",
            "latest_pattern",
            "change_description",
        ],
    )


# ============================================================
# CASHFLOW EXCEL CHECK
# ============================================================

def verify_cashflow_intelligence() -> None:
    if not CASHFLOW_INTELLIGENCE_FILE.exists():
        raise FileNotFoundError(
            f"File not found: {CASHFLOW_INTELLIGENCE_FILE}"
        )

    dataframe = pd.read_excel(
        CASHFLOW_INTELLIGENCE_FILE
    )

    required_column = "capital_allocation_label"

    if required_column not in dataframe.columns:
        raise ValueError(
            f"{required_column} is missing from "
            "cashflow_intelligence.xlsx"
        )

    print(
        "Capital allocation column verified in "
        "cashflow_intelligence.xlsx"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 65)
    print("SPRINT 5 - DAY 32 - CAPITAL ALLOCATION REPORT")
    print("=" * 65)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe, original_pattern_column = (
        load_capital_allocation()
    )

    validate_coverage(dataframe)

    distribution = build_latest_distribution(
        dataframe
    )

    pattern_changes = build_pattern_changes(
        dataframe
    )

    distribution.to_csv(
        PATTERN_DISTRIBUTION_FILE,
        index=False,
    )

    pattern_changes.to_csv(
        PATTERN_CHANGES_FILE,
        index=False,
    )

    verify_cashflow_intelligence()

    company_count = dataframe[
        "company_id"
    ].nunique()

    total_rows = len(dataframe)

    year_count = dataframe[
        "_year_number"
    ].nunique()

    print(f"Companies found           : {company_count}")
    print(f"Company-year rows         : {total_rows}")
    print(f"Years available           : {year_count}")
    print(
        f"Pattern column used       : "
        f"{orig"""
Sprint 5 - Day 33
Company Financial Tearsheet Generator

Generates two-page PDF tearsheets using:
- data/processed/companies.csv
- data/processed/profitandloss.csv
- data/processed/balancesheet.csv
- data/processed/cashflow.csv
- output/pros_cons_generated.csv
- output/capital_allocation.csv

Examples:
    python src/reports/tearsheet.py --company-id 1
    python src/reports/tearsheet.py --all
    python src/reports/tearsheet.py --all --limit 5
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"
REPORT_DIR = PROJECT_ROOT / "reports" / "tearsheets"

COMPANIES_FILE = DATA_DIR / "companies.csv"
PNL_FILE = DATA_DIR / "profitandloss.csv"
BALANCE_SHEET_FILE = DATA_DIR / "balancesheet.csv"
CASHFLOW_FILE = DATA_DIR / "cashflow.csv"
PROS_CONS_FILE = OUTPUT_DIR / "pros_cons_generated.csv"
CAPITAL_ALLOCATION_FILE = OUTPUT_DIR / "capital_allocation.csv"

PAGE_WIDTH, PAGE_HEIGHT = A4

PRIMARY = colors.HexColor("#173B57")
SECONDARY = colors.HexColor("#236B8E")
LIGHT_BLUE = colors.HexColor("#EAF4F8")
LIGHT_GREY = colors.HexColor("#F3F5F7")
MID_GREY = colors.HexColor("#D7DEE3")
DARK_GREY = colors.HexColor("#4C5964")
GREEN = colors.HexColor("#287D4F")
LIGHT_GREEN = colors.HexColor("#EAF6EF")
RED = colors.HexColor("#B33A3A")
LIGHT_RED = colors.HexColor("#FCEEEE")
AMBER = colors.HexColor("#A66A00")
LIGHT_AMBER = colors.HexColor("#FFF5DD")


def validate_input_files() -> None:
    """Raise an error when mandatory input files are missing."""

    required_files = [
        COMPANIES_FILE,
        PNL_FILE,
        BALANCE_SHEET_FILE,
        CASHFLOW_FILE,
        PROS_CONS_FILE,
    ]

    missing = [str(path) for path in required_files if not path.exists()]

    if missing:
        message = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Required files are missing:\n{message}")


def load_data() -> dict[str, pd.DataFrame]:
    """Load and normalize all required datasets."""

    validate_input_files()

    data = {
        "companies": pd.read_csv(COMPANIES_FILE),
        "pnl": pd.read_csv(PNL_FILE),
        "balance_sheet": pd.read_csv(BALANCE_SHEET_FILE),
        "cashflow": pd.read_csv(CASHFLOW_FILE),
        "pros_cons": pd.read_csv(PROS_CONS_FILE),
    }

    if CAPITAL_ALLOCATION_FILE.exists():
        data["capital_allocation"] = pd.read_csv(CAPITAL_ALLOCATION_FILE)
    else:
        data["capital_allocation"] = pd.DataFrame()

    data["companies"]["id"] = pd.to_numeric(
        data["companies"]["id"], errors="coerce"
    ).astype("Int64")

    for key in ["pnl", "balance_sheet", "cashflow", "pros_cons"]:
        company_column = "company_id"

        if company_column in data[key].columns:
            data[key][company_column] = pd.to_numeric(
                data[key][company_column], errors="coerce"
            ).astype("Int64")

    if not data["capital_allocation"].empty:
        data["capital_allocation"]["company_id"] = pd.to_numeric(
            data["capital_allocation"]["company_id"], errors="coerce"
        ).astype("Int64")

    for key in ["pnl", "balance_sheet", "cashflow", "capital_allocation"]:
        if not data[key].empty and "year" in data[key].columns:
            data[key]["year_numeric"] = data[key]["year"].apply(extract_year)

    return data


def extract_year(value: Any) -> int | None:
    """Extract a four-digit financial year from mixed year formats."""

    if pd.isna(value):
        return None

    match = re.search(r"(19|20)\d{2}", str(value))

    if match:
        return int(match.group())

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def safe_number(value: Any, default: float = 0.0) -> float:
    """Convert values to float while safely handling nulls and strings."""

    if pd.isna(value):
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        cleaned = re.sub(r"[^0-9.\-]", "", str(value))

        try:
            return float(cleaned)
        except ValueError:
            return default


def format_number(value: Any, decimals: int = 1) -> str:
    """Format a financial value with commas."""

    if pd.isna(value):
        return "N/A"

    number = safe_number(value)

    if abs(number) >= 1000:
        return f"{number:,.{decimals}f}"

    return f"{number:.{decimals}f}"


def format_percent(value: Any) -> str:
    """Format value as percentage."""

    if pd.isna(value):
        return "N/A"

    return f"{safe_number(value):.1f}%"


def format_currency(value: Any) -> str:
    """Format financial value in crore units."""

    if pd.isna(value):
        return "N/A"

    return f"₹{safe_number(value):,.1f} Cr"


def clean_text(value: Any, fallback: str = "Not available") -> str:
    """Convert null or malformed values into display-safe strings."""

    if pd.isna(value):
        return fallback

    text = str(value).strip()

    if not text or text.lower() in {"nan", "none", "null"}:
        return fallback

    return text


def parse_list_value(value: Any) -> list[str]:
    """
    Parse pros or cons stored as Python lists, separated strings,
    numbered text or single sentences.
    """

    if pd.isna(value):
        return []

    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item) != "Not available"]

    text = str(value).strip()

    if not text:
        return []

    try:
        parsed = ast.literal_eval(text)

        if isinstance(parsed, list):
            return [
                clean_text(item)
                for item in parsed
                if clean_text(item) != "Not available"
            ]
    except (ValueError, SyntaxError):
        pass

    text = text.replace("\\n", "\n")

    candidates = re.split(r"\n|;|\|\||•", text)

    cleaned_items: list[str] = []

    for item in candidates:
        item = re.sub(r"^\s*[\-\*\d.)]+\s*", "", item).strip()

        if item:
            cleaned_items.append(item)

    if len(cleaned_items) == 1 and len(cleaned_items[0]) > 180:
        sentence_parts = re.split(r"(?<=[.!?])\s+", cleaned_items[0])
        cleaned_items = [part.strip() for part in sentence_parts if part.strip()]

    return cleaned_items


def truncate_text(text: str, maximum_length: int) -> str:
    """Prevent exceptionally long company text from overflowing."""

    if len(text) <= maximum_length:
        return text

    return text[: maximum_length - 3].rstrip() + "..."


def get_company_rows(
    dataframe: pd.DataFrame,
    company_id: int,
) -> pd.DataFrame:
    """Return rows belonging to one company."""

    if dataframe.empty or "company_id" not in dataframe.columns:
        return pd.DataFrame()

    result = dataframe[dataframe["company_id"] == company_id].copy()

    if "year_numeric" in result.columns:
        result = result.sort_values("year_numeric")

    return result


def latest_row(dataframe: pd.DataFrame) -> pd.Series:
    """Return latest available row or an empty Series."""

    if dataframe.empty:
        return pd.Series(dtype="object")

    if "year_numeric" in dataframe.columns:
        valid = dataframe[dataframe["year_numeric"].notna()]

        if not valid.empty:
            return valid.sort_values("year_numeric").iloc[-1]

    return dataframe.iloc[-1]


def get_latest_pattern(
    company_id: int,
    pros_cons_row: pd.Series,
    capital_allocation: pd.DataFrame,
) -> str:
    """Get the most recent capital-allocation pattern."""

    generated_pattern = clean_text(
        pros_cons_row.get("capital_allocation_pattern"),
        fallback="",
    )

    if generated_pattern:
        return generated_pattern

    if capital_allocation.empty:
        return "Not available"

    rows = capital_allocation[
        capital_allocation["company_id"] == company_id
    ].copy()

    if rows.empty:
        return "Not available"

    if "year_numeric" in rows.columns:
        rows = rows.sort_values("year_numeric")

    pattern_column = None

    for candidate in [
        "pattern_label",
        "capital_allocation_pattern",
        "pattern",
        "allocation_pattern",
    ]:
        if candidate in rows.columns:
            pattern_column = candidate
            break

    if pattern_column is None:
        return "Not available"

    return clean_text(rows.iloc[-1][pattern_column])


def create_line_chart(
    dataframe: pd.DataFrame,
    columns: list[str],
    labels: list[str],
    title: str,
    output_path: Path,
) -> None:
    """Create a compact financial trend line chart."""

    chart_df = dataframe.copy()

    if chart_df.empty:
        raise ValueError(f"No data available for chart: {title}")

    chart_df = chart_df[chart_df["year_numeric"].notna()].copy()
    chart_df = chart_df.sort_values("year_numeric").tail(10)

    figure, axis = plt.subplots(figsize=(7.2, 2.7))

    valid_series = 0

    for column, label in zip(columns, labels):
        if column not in chart_df.columns:
            continue

        values = pd.to_numeric(chart_df[column], errors="coerce")

        if values.notna().sum() == 0:
            continue

        axis.plot(
            chart_df["year_numeric"],
            values,
            marker="o",
            linewidth=2,
            label=label,
        )

        valid_series += 1

    if valid_series == 0:
        plt.close(figure)
        raise ValueError(f"No numeric series available for chart: {title}")

    axis.set_title(title, fontsize=11, fontweight="bold")
    axis.set_xlabel("Financial Year", fontsize=8)
    axis.set_ylabel("₹ Crore", fontsize=8)
    axis.tick_params(axis="both", labelsize=7)
    axis.grid(True, alpha=0.25)

    if valid_series > 1:
        axis.legend(fontsize=7, loc="best")

    figure.tight_layout()
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def build_styles() -> dict[str, ParagraphStyle]:
    """Create reusable PDF paragraph styles."""

    base_styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CompanyTitle",
            parent=base_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=22,
            textColor=PRIMARY,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=DARK_GREY,
        ),
        "section": ParagraphStyle(
            "SectionHeading",
            parent=base_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.white,
            backColor=PRIMARY,
            borderPadding=(4, 6, 4, 6),
            spaceBefore=5,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#26343D"),
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=DARK_GREY,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            textColor=DARK_GREY,
            alignment=TA_CENTER,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=PRIMARY,
            alignment=TA_CENTER,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            leftIndent=8,
            firstLineIndent=-5,
            spaceAfter=3,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=6.5,
            leading=8,
            textColor=DARK_GREY,
            alignment=TA_CENTER,
        ),
    }


def metric_card(
    label: str,
    value: str,
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Build one KPI card."""

    table = Table(
        [
            [Paragraph(value, styles["metric_value"])],
            [Paragraph(label, styles["metric_label"])],
        ],
        colWidths=[37 * mm],
        rowHeights=[10 * mm, 8 * mm],
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, MID_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    return table


def build_metrics_grid(
    metrics: list[tuple[str, str]],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Arrange KPI cards into one horizontal row."""

    cards = [metric_card(label, value, styles) for label, value in metrics]

    table = Table(
        [cards],
        colWidths=[39 * mm] * len(cards),
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )

    return table


def create_financial_table(
    headers: list[str],
    rows: list[list[str]],
    column_widths: list[float],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create a styled financial summary table."""

    formatted_rows = [
        [Paragraph(str(cell), styles["small"]) for cell in headers]
    ]

    for row in rows:
        formatted_rows.append(
            [Paragraph(str(cell), styles["small"]) for cell in row]
        )

    table = Table(
        formatted_rows,
        colWidths=column_widths,
        repeatRows=1,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
                ("GRID", (0, 0), (-1, -1), 0.4, MID_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return table


def create_bullet_box(
    heading: str,
    items: list[str],
    positive: bool,
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create pros or cons box."""

    background = LIGHT_GREEN if positive else LIGHT_RED
    heading_color = GREEN if positive else RED
    bullet_symbol = "✓" if positive else "•"

    if not items:
        items = ["No significant rule-based observations were generated."]

    items = items[:5]

    content: list[Flowable] = [
        Paragraph(
            heading,
            ParagraphStyle(
                f"{heading}Style",
                parent=styles["body"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=12,
                textColor=heading_color,
                spaceAfter=5,
            ),
        )
    ]

    for item in items:
        safe_item = truncate_text(clean_text(item), 230)
        content.append(
            Paragraph(
                f"{bullet_symbol} {safe_item}",
                styles["bullet"],
            )
        )

    table = Table(
        [[content]],
        colWidths=[88 * mm],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, heading_color),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    return table


def add_page_header_footer(
    canvas,
    document,
    company_name: str,
) -> None:
    """Draw consistent page header and footer."""

    canvas.saveState()

    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_HEIGHT - 13 * mm, PAGE_WIDTH, 13 * mm, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(
        15 * mm,
        PAGE_HEIGHT - 8.5 * mm,
        "N100 FINANCIAL INTELLIGENCE",
    )

    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(
        PAGE_WIDTH - 15 * mm,
        PAGE_HEIGHT - 8.5 * mm,
        truncate_text(company_name, 55),
    )

    canvas.setStrokeColor(MID_GREY)
    canvas.line(
        15 * mm,
        12 * mm,
        PAGE_WIDTH - 15 * mm,
        12 * mm,
    )

    canvas.setFillColor(DARK_GREY)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(
        15 * mm,
        7.5 * mm,
        "Generated from processed financial data. For analytical use only.",
    )

    canvas.drawRightString(
        PAGE_WIDTH - 15 * mm,
        7.5 * mm,
        f"Page {document.page}",
    )

    canvas.restoreState()


def build_tearsheet(
    company_id: int,
    data: dict[str, pd.DataFrame],
) -> Path:
    """Generate a two-page PDF tearsheet for one company."""

    company_rows = data["companies"][data["companies"]["id"] == company_id]

    if company_rows.empty:
        raise ValueError(f"Company ID {company_id} was not found.")

    company = company_rows.iloc[0]

    pnl = get_company_rows(data["pnl"], company_id)
    balance_sheet = get_company_rows(data["balance_sheet"], company_id)
    cashflow = get_company_rows(data["cashflow"], company_id)

    pros_cons_rows = data["pros_cons"][
        data["pros_cons"]["company_id"] == company_id
    ]

    if pros_cons_rows.empty:
        pros_cons = pd.Series(dtype="object")
    else:
        pros_cons = pros_cons_rows.iloc[-1]

    latest_pnl = latest_row(pnl)
    latest_balance = latest_row(balance_sheet)
    latest_cashflow = latest_row(cashflow)

    company_name = clean_text(
        company.get("company_name"),
        fallback=f"Company {company_id}",
    )

    safe_filename = re.sub(r"[^A-Za-z0-9_-]+", "_", company_name).strip("_")
    safe_filename = safe_filename[:90] or f"company_{company_id}"

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = REPORT_DIR / f"{company_id}_{safe_filename}_tearsheet.pdf"

    styles = build_styles()

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)

        profit_chart_path = temporary_path / "profit_chart.png"
        cashflow_chart_path = temporary_path / "cashflow_chart.png"

        profit_chart_created = False
        cashflow_chart_created = False

        try:
            create_line_chart(
                pnl,
                ["sales", "net_profit"],
                ["Sales", "Net Profit"],
                "Revenue and Profit Trend",
                profit_chart_path,
            )
            profit_chart_created = True
        except ValueError:
            pass

        try:
            create_line_chart(
                cashflow,
                [
                    "operating_activity",
                    "investing_activity",
                    "financing_activity",
                ],
                [
                    "Operating",
                    "Investing",
                    "Financing",
                ],
                "Cash Flow Trend",
                cashflow_chart_path,
            )
            cashflow_chart_created = True
        except ValueError:
            pass

        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=19 * mm,
            bottomMargin=16 * mm,
            title=f"{company_name} Financial Tearsheet",
            author="N100 Financial Intelligence",
            subject="Company Financial Analysis",
        )

        story: list[Flowable] = []

        broad_sector = clean_text(
            pros_cons.get("broad_sector"),
            fallback="Sector not available",
        )
        sub_sector = clean_text(
            pros_cons.get("sub_sector"),
            fallback="",
        )

        sector_text = broad_sector

        if sub_sector:
            sector_text += f" | {sub_sector}"

        story.append(Paragraph(company_name, styles["title"]))
        story.append(
            Paragraph(
                f"Company ID: {company_id} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"{sector_text}",
                styles["subtitle"],
            )
        )
        story.append(Spacer(1, 3 * mm))

        about_company = truncate_text(
            clean_text(company.get("about_company")),
            800,
        )

        story.append(Paragraph("Company Overview", styles["section"]))
        story.append(Paragraph(about_company, styles["body"]))
        story.append(Spacer(1, 3 * mm))

        metrics = [
            ("ROE", format_percent(company.get("roe_percentage"))),
            ("ROCE", format_percent(company.get("roce_percentage"))),
            ("Book Value", format_number(company.get("book_value"))),
            ("Face Value", format_number(company.get("face_value"))),
        ]

        story.append(build_metrics_grid(metrics, styles))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("Financial Performance", styles["section"]))

        if profit_chart_created:
            story.append(
                Image(
                    str(profit_chart_path),
                    width=178 * mm,
                    height=66 * mm,
                )
            )
        else:
            story.append(
                Paragraph(
                    "Revenue and profit trend data is unavailable.",
                    styles["body"],
                )
            )

        story.append(Spacer(1, 3 * mm))

        latest_year = clean_text(
            latest_pnl.get("year"),
            fallback="Latest",
        )

        pnl_rows = [
            [
                latest_year,
                format_currency(latest_pnl.get("sales")),
                format_currency(latest_pnl.get("operating_profit")),
                format_percent(latest_pnl.get("opm_percentage")),
                format_currency(latest_pnl.get("net_profit")),
                format_number(latest_pnl.get("eps")),
            ]
        ]

        story.append(
            create_financial_table(
                [
                    "Year",
                    "Sales",
                    "Operating Profit",
                    "OPM",
                    "Net Profit",
                    "EPS",
                ],
                pnl_rows,
                [
                    20 * mm,
                    29 * mm,
                    34 * mm,
                    21 * mm,
                    29 * mm,
                    25 * mm,
                ],
                styles,
            )
        )

        story.append(PageBreak())

        story.append(Paragraph("Balance Sheet Snapshot", styles["section"]))

        balance_rows = [
            [
                clean_text(latest_balance.get("year"), fallback="Latest"),
                format_currency(latest_balance.get("equity_capital")),
                format_currency(latest_balance.get("reserves")),
                format_currency(latest_balance.get("borrowings")),
                format_currency(latest_balance.get("fixed_assets")),
                format_currency(latest_balance.get("total_assets")),
            ]
        ]

        story.append(
            create_financial_table(
                [
                    "Year",
                    "Equity",
                    "Reserves",
                    "Borrowings",
                    "Fixed Assets",
                    "Total Assets",
                ],
                balance_rows,
                [
                    20 * mm,
                    26 * mm,
                    28 * mm,
                    28 * mm,
                    30 * mm,
                    30 * mm,
                ],
                styles,
            )
        )

        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Cash Flow Intelligence", styles["section"]))

        cfo_quality = clean_text(
            pros_cons.get("cfo_quality_label"),
            fallback="Not available",
        )

        capital_pattern = get_latest_pattern(
            company_id,
            pros_cons,
            data["capital_allocation"],
        )

        cashflow_metrics = [
            ("CFO Quality", truncate_text(cfo_quality, 24)),
            ("Capital Allocation", truncate_text(capital_pattern, 25)),
            (
                "Operating Cash Flow",
                format_currency(latest_cashflow.get("operating_activity")),
            ),
            (
                "Net Cash Flow",
                format_currency(latest_cashflow.get("net_cash_flow")),
            ),
        ]

        story.append(build_metrics_grid(cashflow_metrics, styles))
        story.append(Spacer(1, 3 * mm))

        if cashflow_chart_created:
            story.append(
                Image(
                    str(cashflow_chart_path),
                    width=178 * mm,
                    height=63 * mm,
                )
            )
        else:
            story.append(
                Paragraph(
                    "Cash-flow trend data is unavailable.",
                    styles["body"],
                )
            )

        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("AI-Generated Investment Observations", styles["section"]))

        pros = parse_list_value(pros_cons.get("pros"))
        cons = parse_list_value(pros_cons.get("cons"))

        pros_box = create_bullet_box(
            "Strengths / Pros",
            pros,
            positive=True,
            styles=styles,
        )

        cons_box = create_bullet_box(
            "Risks / Cons",
            cons,
            positive=False,
            styles=styles,
        )

        observation_table = Table(
            [[pros_box, cons_box]],
            colWidths=[89 * mm, 89 * mm],
            hAlign="LEFT",
        )

        observation_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        story.append(KeepTogether(observation_table))
        story.append(Spacer(1, 3 * mm))

        confidence = pros_cons.get("confidence_score")

        if pd.isna(confidence):
            confidence_text = "N/A"
        else:
            confidence_number = safe_number(confidence)

            if confidence_number <= 1:
                confidence_number *= 100

            confidence_text = f"{confidence_number:.1f}%"

        rules_triggered = clean_text(
            pros_cons.get("rules_triggered"),
            fallback="N/A",
        )

        rules_evaluated = clean_text(
            pros_cons.get("rules_evaluated"),
            fallback="N/A",
        )

        footer_note = (
            f"<b>Confidence score:</b> {confidence_text} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Rules triggered:</b> {rules_triggered} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Rules evaluated:</b> {rules_evaluated}<br/>"
            "Observations are generated from predefined financial rules and "
            "should not be treated as investment advice."
        )

        story.append(
            Table(
                [[Paragraph(footer_note, styles["small"])]],
                colWidths=[178 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_AMBER),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D6B05C")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                ),
            )
        )

        document.build(
            story,
            onFirstPage=lambda canvas, doc: add_page_header_footer(
                canvas,
                doc,
                company_name,
            ),
            onLaterPages=lambda canvas, doc: add_page_header_footer(
                canvas,
                doc,
                company_name,
            ),
        )

    return output_path


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Generate company financial tearsheet PDFs."
    )

    selection = parser.add_mutually_exclusive_group(required=True)

    selection.add_argument(
        "--company-id",
        type=int,
        help="Generate a tearsheet for one company ID.",
    )

    selection.add_argument(
        "--all",
        action="store_true",
        help="Generate tearsheets for every available company.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of companies when using --all.",
    )

    return parser.parse_args()


def main() -> None:
    """Run tearsheet generation."""

    arguments = parse_arguments()

    try:
        data = load_data()
    except Exception as error:
        print(f"\nData loading failed: {error}")
        sys.exit(1)

    company_ids = (
        data["companies"]["id"]
        .dropna()
        .astype(int)
        .drop_duplicates()
        .tolist()
    )

    if arguments.company_id is not None:
        company_ids = [arguments.company_id]

    if arguments.all and arguments.limit is not None:
        company_ids = company_ids[: arguments.limit]

    print("\nSPRINT 5 - DAY 33 - PDF TEARSHEET GENERATOR\n")
    print(f"Companies selected : {len(company_ids)}")
    print(f"Output directory   : {REPORT_DIR}\n")

    successful = 0
    failed = 0

    for index, company_id in enumerate(company_ids, start=1):
        try:
            output_path = build_tearsheet(company_id, data)
            successful += 1
            print(
                f"[{index}/{len(company_ids)}] "
                f"Created: {output_path.name}"
            )
        except Exception as error:
            failed += 1
            print(
                f"[{index}/{len(company_ids)}] "
                f"Failed company {company_id}: {error}"
            )

    print("\nGeneration summary")
    print("------------------")
    print(f"Successful : {successful}")
    print(f"Failed     : {failed}")
    print(f"Total      : {len(company_ids)}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()inal_pattern_column}"
    )
    print(
        f"Latest-year patterns      : "
        f"{len(distribution)}"
    )
    print(
        f"Companies with changes    : "
        f"{len(pattern_changes)}"
    )

    print()
    print("Latest-year distribution:")
    print(distribution.to_string(index=False))

    print()
    print(f"Created: {PATTERN_DISTRIBUTION_FILE}")
    print(f"Created: {PATTERN_CHANGES_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()