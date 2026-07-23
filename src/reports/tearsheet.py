from __future__ import annotations

import argparse
import ast
import re
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
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
BALANCE_FILE = DATA_DIR / "balancesheet.csv"
CASHFLOW_FILE = DATA_DIR / "cashflow.csv"
PROS_CONS_FILE = OUTPUT_DIR / "pros_cons_generated.csv"
CAPITAL_ALLOCATION_FILE = OUTPUT_DIR / "capital_allocation.csv"

PRIMARY = colors.HexColor("#173B57")
LIGHT_BLUE = colors.HexColor("#EAF4F8")
LIGHT_GREY = colors.HexColor("#F3F5F7")
MID_GREY = colors.HexColor("#D7DEE3")
DARK_GREY = colors.HexColor("#4C5964")
GREEN = colors.HexColor("#287D4F")
LIGHT_GREEN = colors.HexColor("#EAF6EF")
RED = colors.HexColor("#B33A3A")
LIGHT_RED = colors.HexColor("#FCEEEE")


def clean_text(value, fallback="Not available"):
    if pd.isna(value):
        return fallback

    text = str(value).strip()

    if not text or text.lower() in {"nan", "none", "null"}:
        return fallback

    return text


def safe_number(value, default=0.0):
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


def format_currency(value):
    if pd.isna(value):
        return "N/A"

    return f"Rs. {safe_number(value):,.1f} Cr"


def format_percent(value):
    if pd.isna(value):
        return "N/A"

    return f"{safe_number(value):.1f}%"


def format_number(value):
    if pd.isna(value):
        return "N/A"

    return f"{safe_number(value):,.1f}"


def extract_year(value):
    if pd.isna(value):
        return None

    match = re.search(r"(19|20)\d{2}", str(value))

    if match:
        return int(match.group())

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_list(value):
    if pd.isna(value):
        return []

    text = str(value).strip()

    if not text:
        return []

    try:
        parsed = ast.literal_eval(text)

        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (ValueError, SyntaxError):
        pass

    parts = re.split(r"\n|;|\|\||•", text)

    result = []

    for part in parts:
        item = re.sub(r"^\s*[\-\*\d.)]+\s*", "", part).strip()

        if item:
            result.append(item)

    return result


def truncate(text, limit):
    text = clean_text(text)

    if len(text) <= limit:
        return text

    return text[: limit - 3].rstrip() + "..."


def load_data():
    required_files = [
        COMPANIES_FILE,
        PNL_FILE,
        BALANCE_FILE,
        CASHFLOW_FILE,
        PROS_CONS_FILE,
    ]

    missing = [path for path in required_files if not path.exists()]

    if missing:
        missing_text = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing required files:\n{missing_text}")

    data = {
        "companies": pd.read_csv(COMPANIES_FILE),
        "pnl": pd.read_csv(PNL_FILE),
        "balance": pd.read_csv(BALANCE_FILE),
        "cashflow": pd.read_csv(CASHFLOW_FILE),
        "pros_cons": pd.read_csv(PROS_CONS_FILE),
    }

    if CAPITAL_ALLOCATION_FILE.exists():
        data["capital_allocation"] = pd.read_csv(CAPITAL_ALLOCATION_FILE)
    else:
        data["capital_allocation"] = pd.DataFrame()

    data["companies"]["id"] = (
        data["companies"]["id"]
        .astype(str)
        .str.strip()
    )

    for key in ["pnl", "balance", "cashflow", "pros_cons"]:
        data[key]["company_id"] = (
            data[key]["company_id"]
            .astype(str)
            .str.strip()
    )

    if not data["capital_allocation"].empty:
        data["capital_allocation"]["company_id"] = (
            data["capital_allocation"]["company_id"]
                .astype(str)
                .str.strip()
        )

    for key in ["pnl", "balance", "cashflow", "capital_allocation"]:
        if not data[key].empty and "year" in data[key].columns:
            data[key]["year_numeric"] = data[key]["year"].apply(extract_year)

    return data


def company_rows(dataframe, company_id):
    if dataframe.empty or "company_id" not in dataframe.columns:
        return pd.DataFrame()

    rows = dataframe[dataframe["company_id"] == company_id].copy()

    if "year_numeric" in rows.columns:
        rows = rows.sort_values("year_numeric")

    return rows


def latest_row(dataframe):
    if dataframe.empty:
        return pd.Series(dtype="object")

    if "year_numeric" in dataframe.columns:
        valid = dataframe[dataframe["year_numeric"].notna()]

        if not valid.empty:
            return valid.sort_values("year_numeric").iloc[-1]

    return dataframe.iloc[-1]


def latest_capital_pattern(company_id, pros_cons_row, allocation_data):
    pattern = clean_text(
        pros_cons_row.get("capital_allocation_pattern"),
        fallback="",
    )

    if pattern:
        return pattern

    if allocation_data.empty:
        return "Not available"

    rows = allocation_data[
        allocation_data["company_id"] == company_id
    ].copy()

    if rows.empty:
        return "Not available"

    if "year_numeric" in rows.columns:
        rows = rows.sort_values("year_numeric")

    for column in [
        "pattern_label",
        "capital_allocation_pattern",
        "pattern",
    ]:
        if column in rows.columns:
            return clean_text(rows.iloc[-1][column])

    return "Not available"


def create_chart(dataframe, columns, labels, title, output_path):
    if dataframe.empty:
        return False

    chart_data = dataframe[
        dataframe["year_numeric"].notna()
    ].copy()

    chart_data = chart_data.sort_values("year_numeric").tail(10)

    if chart_data.empty:
        return False

    figure, axis = plt.subplots(figsize=(7.2, 2.6))

    plotted = 0

    for column, label in zip(columns, labels):
        if column not in chart_data.columns:
            continue

        values = pd.to_numeric(chart_data[column], errors="coerce")

        if values.notna().sum() == 0:
            continue

        axis.plot(
            chart_data["year_numeric"],
            values,
            marker="o",
            linewidth=2,
            label=label,
        )

        plotted += 1

    if plotted == 0:
        plt.close(figure)
        return False

    axis.set_title(title, fontsize=11, fontweight="bold")
    axis.set_xlabel("Financial Year", fontsize=8)
    axis.set_ylabel("Rs. Crore", fontsize=8)
    axis.tick_params(axis="both", labelsize=7)
    axis.grid(True, alpha=0.25)

    if plotted > 1:
        axis.legend(fontsize=7)

    figure.tight_layout()
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)

    return True


def build_styles():
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=21,
            textColor=PRIMARY,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=DARK_GREY,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.white,
            backColor=PRIMARY,
            borderPadding=5,
            spaceBefore=4,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontSize=8,
            leading=11,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontSize=7,
            leading=9,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=PRIMARY,
            alignment=1,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["Normal"],
            fontSize=7,
            leading=8,
            textColor=DARK_GREY,
            alignment=1,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontSize=7.5,
            leading=10,
            leftIndent=8,
            firstLineIndent=-5,
            spaceAfter=3,
        ),
    }


def metric_card(label, value, styles):
    table = Table(
        [
            [Paragraph(value, styles["metric_value"])],
            [Paragraph(label, styles["metric_label"])],
        ],
        colWidths=[41 * mm],
        rowHeights=[10 * mm, 8 * mm],
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, MID_GREY),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    return table


def metric_grid(metrics, styles):
    cards = [metric_card(label, value, styles) for label, value in metrics]

    table = Table(
        [cards],
        colWidths=[43 * mm] * len(cards),
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


def financial_table(headers, rows, widths, styles):
    data = [
        [Paragraph(str(cell), styles["small"]) for cell in headers]
    ]

    for row in rows:
        data.append(
            [Paragraph(str(cell), styles["small"]) for cell in row]
        )

    table = Table(data, colWidths=widths, repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
                ("GRID", (0, 0), (-1, -1), 0.4, MID_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return table


def observation_box(title, items, positive, styles):
    background = LIGHT_GREEN if positive else LIGHT_RED
    border = GREEN if positive else RED

    content = [
        Paragraph(
            title,
            ParagraphStyle(
                title,
                parent=styles["body"],
                fontName="Helvetica-Bold",
                fontSize=10,
                textColor=border,
                spaceAfter=5,
            ),
        )
    ]

    if not items:
        items = ["No significant observations generated."]

    for item in items[:5]:
        content.append(
            Paragraph(
                f"• {truncate(item, 220)}",
                styles["bullet"],
            )
        )

    table = Table([[content]], colWidths=[87 * mm])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    return table


def add_header_footer(canvas, document, company_name):
    page_width, page_height = A4

    canvas.saveState()

    canvas.setFillColor(PRIMARY)
    canvas.rect(
        0,
        page_height - 13 * mm,
        page_width,
        13 * mm,
        fill=1,
        stroke=0,
    )

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(
        15 * mm,
        page_height - 8.5 * mm,
        "N100 FINANCIAL INTELLIGENCE",
    )

    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(
        page_width - 15 * mm,
        page_height - 8.5 * mm,
        truncate(company_name, 50),
    )

    canvas.setStrokeColor(MID_GREY)
    canvas.line(
        15 * mm,
        12 * mm,
        page_width - 15 * mm,
        12 * mm,
    )

    canvas.setFillColor(DARK_GREY)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(
        15 * mm,
        7.5 * mm,
        "Generated for analytical use only.",
    )

    canvas.drawRightString(
        page_width - 15 * mm,
        7.5 * mm,
        f"Page {document.page}",
    )

    canvas.restoreState()


def build_tearsheet(company_id, data):
    company_rows_data = data["companies"][
        data["companies"]["id"] == company_id
    ]

    if company_rows_data.empty:
        raise ValueError(f"Company ID {company_id} was not found.")

    company = company_rows_data.iloc[0]

    pnl = company_rows(data["pnl"], company_id)
    balance = company_rows(data["balance"], company_id)
    cashflow = company_rows(data["cashflow"], company_id)

    pros_rows = data["pros_cons"][
        data["pros_cons"]["company_id"] == company_id
    ]

    if pros_rows.empty:
        pros_cons = pd.Series(dtype="object")
    else:
        pros_cons = pros_rows.iloc[-1]

    latest_pnl = latest_row(pnl)
    latest_balance = latest_row(balance)
    latest_cashflow = latest_row(cashflow)

    company_name = clean_text(
        company.get("company_name"),
        f"Company {company_id}",
    )

    filename = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        company_name,
    ).strip("_")

    filename = filename[:80] or f"company_{company_id}"

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = (
        REPORT_DIR
        / f"{company_id}_{filename}_tearsheet.pdf"
    )

    styles = build_styles()

    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory)

        profit_chart_path = temp_path / "profit_chart.png"
        cashflow_chart_path = temp_path / "cashflow_chart.png"

        profit_chart_created = create_chart(
            pnl,
            ["sales", "net_profit"],
            ["Sales", "Net Profit"],
            "Revenue and Profit Trend",
            profit_chart_path,
        )

        cashflow_chart_created = create_chart(
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

        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=19 * mm,
            bottomMargin=16 * mm,
            title=f"{company_name} Financial Tearsheet",
        )

        story = []

        broad_sector = clean_text(
            pros_cons.get("broad_sector"),
            "Sector not available",
        )

        sub_sector = clean_text(
            pros_cons.get("sub_sector"),
            "",
        )

        sector_text = broad_sector

        if sub_sector:
            sector_text += f" | {sub_sector}"

        story.append(Paragraph(company_name, styles["title"]))
        story.append(
            Paragraph(
                f"Company ID: {company_id} | {sector_text}",
                styles["subtitle"],
            )
        )

        story.append(Spacer(1, 3 * mm))
        story.append(
            Paragraph(
                "Company Overview",
                styles["section"],
            )
        )

        story.append(
            Paragraph(
                truncate(company.get("about_company"), 750),
                styles["body"],
            )
        )

        story.append(Spacer(1, 3 * mm))

        story.append(
            metric_grid(
                [
                    (
                        "ROE",
                        format_percent(
                            company.get("roe_percentage")
                        ),
                    ),
                    (
                        "ROCE",
                        format_percent(
                            company.get("roce_percentage")
                        ),
                    ),
                    (
                        "Book Value",
                        format_number(
                            company.get("book_value")
                        ),
                    ),
                    (
                        "Face Value",
                        format_number(
                            company.get("face_value")
                        ),
                    ),
                ],
                styles,
            )
        )

        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                "Financial Performance",
                styles["section"],
            )
        )

        if profit_chart_created:
            story.append(
                Image(
                    str(profit_chart_path),
                    width=178 * mm,
                    height=64 * mm,
                )
            )
        else:
            story.append(
                Paragraph(
                    "Revenue and profit trend data unavailable.",
                    styles["body"],
                )
            )

        story.append(Spacer(1, 3 * mm))

        story.append(
            financial_table(
                [
                    "Year",
                    "Sales",
                    "Operating Profit",
                    "OPM",
                    "Net Profit",
                    "EPS",
                ],
                [
                    [
                        clean_text(
                            latest_pnl.get("year"),
                            "Latest",
                        ),
                        format_currency(
                            latest_pnl.get("sales")
                        ),
                        format_currency(
                            latest_pnl.get("operating_profit")
                        ),
                        format_percent(
                            latest_pnl.get("opm_percentage")
                        ),
                        format_currency(
                            latest_pnl.get("net_profit")
                        ),
                        format_number(
                            latest_pnl.get("eps")
                        ),
                    ]
                ],
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

        story.append(
            Paragraph(
                "Balance Sheet Snapshot",
                styles["section"],
            )
        )

        story.append(
            financial_table(
                [
                    "Year",
                    "Equity",
                    "Reserves",
                    "Borrowings",
                    "Fixed Assets",
                    "Total Assets",
                ],
                [
                    [
                        clean_text(
                            latest_balance.get("year"),
                            "Latest",
                        ),
                        format_currency(
                            latest_balance.get("equity_capital")
                        ),
                        format_currency(
                            latest_balance.get("reserves")
                        ),
                        format_currency(
                            latest_balance.get("borrowings")
                        ),
                        format_currency(
                            latest_balance.get("fixed_assets")
                        ),
                        format_currency(
                            latest_balance.get("total_assets")
                        ),
                    ]
                ],
                [
                    20 * mm,
                    27 * mm,
                    28 * mm,
                    29 * mm,
                    31 * mm,
                    31 * mm,
                ],
                styles,
            )
        )

        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                "Cash Flow Intelligence",
                styles["section"],
            )
        )

        cfo_quality = clean_text(
            pros_cons.get("cfo_quality_label")
        )

        allocation_pattern = latest_capital_pattern(
            company_id,
            pros_cons,
            data["capital_allocation"],
        )

        story.append(
            metric_grid(
                [
                    (
                        "CFO Quality",
                        truncate(cfo_quality, 20),
                    ),
                    (
                        "Capital Allocation",
                        truncate(allocation_pattern, 20),
                    ),
                    (
                        "Operating Cash Flow",
                        format_currency(
                            latest_cashflow.get(
                                "operating_activity"
                            )
                        ),
                    ),
                    (
                        "Net Cash Flow",
                        format_currency(
                            latest_cashflow.get(
                                "net_cash_flow"
                            )
                        ),
                    ),
                ],
                styles,
            )
        )

        story.append(Spacer(1, 3 * mm))

        if cashflow_chart_created:
            story.append(
                Image(
                    str(cashflow_chart_path),
                    width=178 * mm,
                    height=61 * mm,
                )
            )
        else:
            story.append(
                Paragraph(
                    "Cash flow trend data unavailable.",
                    styles["body"],
                )
            )

        story.append(Spacer(1, 3 * mm))
        story.append(
            Paragraph(
                "AI-Generated Investment Observations",
                styles["section"],
            )
        )

        pros = parse_list(pros_cons.get("pros"))
        cons = parse_list(pros_cons.get("cons"))

        observations = Table(
            [
                [
                    observation_box(
                        "Strengths / Pros",
                        pros,
                        True,
                        styles,
                    ),
                    observation_box(
                        "Risks / Cons",
                        cons,
                        False,
                        styles,
                    ),
                ]
            ],
            colWidths=[89 * mm, 89 * mm],
        )

        observations.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        story.append(observations)
        story.append(Spacer(1, 3 * mm))

        confidence = pros_cons.get("confidence_score")

        if pd.isna(confidence):
            confidence_text = "N/A"
        else:
            confidence_value = safe_number(confidence)

            if confidence_value <= 1:
                confidence_value *= 100

            confidence_text = f"{confidence_value:.1f}%"

        note = (
            f"<b>Confidence score:</b> {confidence_text} | "
            f"<b>Rules triggered:</b> "
            f"{clean_text(pros_cons.get('rules_triggered'), 'N/A')} | "
            f"<b>Rules evaluated:</b> "
            f"{clean_text(pros_cons.get('rules_evaluated'), 'N/A')}<br/>"
            "This report is generated from predefined financial rules "
            "and should not be treated as investment advice."
        )

        note_table = Table(
            [[Paragraph(note, styles["small"])]],
            colWidths=[178 * mm],
        )

        note_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#FFF5DD"),
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#D6B05C"),
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        story.append(note_table)

        document.build(
            story,
            onFirstPage=lambda canvas, doc: add_header_footer(
                canvas,
                doc,
                company_name,
            ),
            onLaterPages=lambda canvas, doc: add_header_footer(
                canvas,
                doc,
                company_name,
            ),
        )

    return output_path


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate financial tearsheet PDFs."
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--company-id",
        type=str,
        help="Generate one company tearsheet.",
    )

    group.add_argument(
        "--all",
        action="store_true",
        help="Generate tearsheets for all companies.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of companies with --all.",
    )

    return parser.parse_args()


def main():
    arguments = parse_arguments()

    try:
        data = load_data()
    except Exception as error:
        print(f"\nData loading failed: {error}")
        sys.exit(1)

    company_ids = (
        data["companies"]["id"]
        .dropna()
        .astype(str)
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

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()