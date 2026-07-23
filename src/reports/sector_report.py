from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"
REPORT_DIR = PROJECT_ROOT / "reports" / "sector"
CHART_DIR = REPORT_DIR / "charts"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
CHART_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "companies": PROCESSED_DIR / "companies.csv",
    "sectors": PROCESSED_DIR / "sectors.csv",
    "peer_groups": PROCESSED_DIR / "peer_groups.csv",
    "profit_loss": PROCESSED_DIR / "profitandloss.csv",
    "balance_sheet": PROCESSED_DIR / "balancesheet.csv",
    "cashflow": PROCESSED_DIR / "cashflow.csv",
    "pros_cons": OUTPUT_DIR / "pros_cons_generated.csv",
    "capital_allocation": OUTPUT_DIR / "capital_allocation.csv",
    "peer_percentiles": OUTPUT_DIR / "peer_percentiles.csv",
}

def clean_text(value: Any, default: str = "N/A") -> str:
    if value is None or pd.isna(value):
        return default
    text = re.sub(r"\s+", " ", str(value).replace("\\n", " ").replace("\n", " ")).strip()
    return text or default

def clean_id(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()

def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", clean_text(value, "unknown").lower()).strip("_")

def safe_num(value: Any, decimals: int = 1) -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"

def safe_pct(value: Any, decimals: int = 1) -> str:
    text = safe_num(value, decimals)
    return text if text == "N/A" else f"{text}%"

def year_value(value: Any) -> int:
    match = re.search(r"(19|20)\d{2}", clean_text(value, ""))
    return int(match.group()) if match else -1

def split_statements(value: Any) -> list[str]:
    if value is None or pd.isna(value):
        return []
    result = []
    for part in re.split(r"\s*\|\s*|\s*;\s*|\n+", str(value)):
        text = re.sub(r"^[•\-\d.)\s]+", "", clean_text(part, "")).strip()
        if text:
            result.append(text)
    return result

def read_required(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file missing: {name}\n{path}")
    return pd.read_csv(path)

def read_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

def load_data() -> dict[str, pd.DataFrame]:
    data = {
        "companies": read_required(FILES["companies"], "companies.csv"),
        "sectors": read_required(FILES["sectors"], "sectors.csv"),
        "peer_groups": read_optional(FILES["peer_groups"]),
        "profit_loss": read_required(FILES["profit_loss"], "profitandloss.csv"),
        "balance_sheet": read_required(FILES["balance_sheet"], "balancesheet.csv"),
        "cashflow": read_required(FILES["cashflow"], "cashflow.csv"),
        "pros_cons": read_required(FILES["pros_cons"], "pros_cons_generated.csv"),
        "capital_allocation": read_optional(FILES["capital_allocation"]),
        "peer_percentiles": read_optional(FILES["peer_percentiles"]),
    }
    data["companies"]["id"] = data["companies"]["id"].apply(clean_id)
    for df in data.values():
        if not df.empty and "company_id" in df.columns:
            df["company_id"] = df["company_id"].apply(clean_id)
    numeric_columns = {
        "companies": ["roe_percentage", "roce_percentage", "book_value", "face_value"],
        "sectors": ["index_weight_pct"],
        "profit_loss": ["sales", "operating_profit", "opm_percentage", "net_profit", "eps", "dividend_payout"],
        "balance_sheet": ["borrowings", "reserves", "total_assets", "total_liabilities"],
        "cashflow": ["operating_activity", "investing_activity", "financing_activity", "net_cash_flow"],
        "pros_cons": ["confidence_score", "latest_roe_pct", "latest_opm_pct", "debt_to_equity", "interest_coverage", "revenue_cagr_5yr", "pat_cagr_5yr", "eps_cagr_5yr", "latest_fcf_cr", "dividend_yield_pct", "pe_ratio", "pb_ratio"],
        "peer_percentiles": ["value", "percentile_rank"],
    }
    for name, columns in numeric_columns.items():
        df = data[name]
        if df.empty:
            continue
        for column in columns:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
    return data

def latest_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    result = df.copy()
    if "year" in result.columns:
        result["_year_sort"] = result["year"].apply(year_value)
        result = result.sort_values(["company_id", "_year_sort"]).drop_duplicates("company_id", keep="last")
        result = result.drop(columns=["_year_sort"])
    else:
        result = result.drop_duplicates("company_id", keep="last")
    return result

def available_sectors(data: dict[str, pd.DataFrame]) -> list[str]:
    values = data["sectors"]["broad_sector"].dropna().astype(str).str.strip()
    return sorted(values[values != ""].unique().tolist())

def sector_frame(sector: str, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    sector_rows = data["sectors"][data["sectors"]["broad_sector"].astype(str).str.lower() == sector.lower()].copy()
    result = sector_rows.merge(data["companies"], left_on="company_id", right_on="id", how="left", suffixes=("", "_company"))
    if "id" in result.columns:
        result = result.drop(columns=["id"])
    result = result.merge(latest_rows(data["profit_loss"]), on="company_id", how="left", suffixes=("", "_pnl"))
    result = result.merge(latest_rows(data["balance_sheet"]), on="company_id", how="left", suffixes=("", "_balance"))
    result = result.merge(latest_rows(data["cashflow"]), on="company_id", how="left", suffixes=("", "_cashflow"))
    pros = data["pros_cons"][data["pros_cons"]["broad_sector"].astype(str).str.lower() == sector.lower()].drop_duplicates("company_id", keep="last")
    result = result.merge(pros, on="company_id", how="left", suffixes=("", "_nlp"))
    if not data["capital_allocation"].empty:
        capital = data["capital_allocation"].drop_duplicates("company_id", keep="last")
        result = result.merge(capital, on="company_id", how="left", suffixes=("", "_capital"))
    return result

def top_metric(df: pd.DataFrame, metric: str, limit: int = 5) -> pd.DataFrame:
    if metric not in df.columns:
        return pd.DataFrame()
    cols = [c for c in ["company_id", "company_name", "sub_sector", metric] if c in df.columns]
    out = df[cols].copy()
    out[metric] = pd.to_numeric(out[metric], errors="coerce")
    return out.dropna(subset=[metric]).sort_values(metric, ascending=False).head(limit)

def common_points(df: pd.DataFrame, column: str, limit: int = 5) -> list[tuple[str, int]]:
    if column not in df.columns:
        return []
    counter: Counter[str] = Counter()
    for value in df[column]:
        for statement in split_statements(value):
            counter[statement.lower()] += 1
    return counter.most_common(limit)

def summary_stats(df: pd.DataFrame) -> dict[str, Any]:
    def mean(column: str) -> float | None:
        if column not in df.columns:
            return None
        values = pd.to_numeric(df[column], errors="coerce").dropna()
        return float(values.mean()) if not values.empty else None
    def total(column: str) -> float:
        if column not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())
    positive_fcf = int((pd.to_numeric(df.get("latest_fcf_cr"), errors="coerce") > 0).sum()) if "latest_fcf_cr" in df.columns else 0
    return {
        "company_count": len(df),
        "index_weight": total("index_weight_pct"),
        "avg_roe": mean("latest_roe_pct"),
        "avg_roce": mean("roce_percentage"),
        "avg_opm": mean("latest_opm_pct"),
        "avg_revenue_growth": mean("revenue_cagr_5yr"),
        "avg_pat_growth": mean("pat_cagr_5yr"),
        "avg_debt_equity": mean("debt_to_equity"),
        "positive_fcf": positive_fcf,
    }

def create_sector_chart(df: pd.DataFrame, sector: str) -> Path | None:
    metric = "latest_roe_pct" if "latest_roe_pct" in df.columns else "roe_percentage"
    chart_df = top_metric(df, metric, 8)
    if chart_df.empty:
        return None
    path = CHART_DIR / f"{slugify(sector)}_roe.png"
    plt.figure(figsize=(9, 5))
    plt.bar(chart_df["company_id"].astype(str), chart_df[metric])
    plt.title(f"{sector} - Top Companies by ROE")
    plt.xlabel("Company")
    plt.ylabel("ROE (%)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path

def build_table(data: list[list[Any]], widths: list[float] | None = None) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F9")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table

def page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(285 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()

def generate_sector_pdf(sector: str, data: dict[str, pd.DataFrame]) -> Path:
    df = sector_frame(sector, data)
    if df.empty:
        raise ValueError(f"No companies found for sector: {sector}")
    stats = summary_stats(df)
    output_path = REPORT_DIR / f"{slugify(sector)}_sector_report.pdf"
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SectorTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=22, leading=26, textColor=colors.HexColor("#17365D"), spaceAfter=12))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=14, leading=18, textColor=colors.HexColor("#1F4E78"), spaceBefore=8, spaceAfter=8))
    styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontSize=8.5, leading=11, alignment=TA_LEFT))
    doc = SimpleDocTemplate(str(output_path), pagesize=landscape(A4), leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=14*mm, title=f"{sector} Sector Report", author="N100 Financial Intelligence")
    story = [
        Paragraph(f"{sector} Sector Intelligence Report", styles["SectorTitle"]),
        Paragraph("Generated from company financials, cash-flow intelligence, peer analysis, capital-allocation patterns, and NLP-generated strengths and risks.", styles["BodySmall"]),
        Spacer(1, 6*mm),
    ]
    summary_data = [
        ["Metric", "Value", "Metric", "Value"],
        ["Companies", str(stats["company_count"]), "Total Index Weight", safe_pct(stats["index_weight"])],
        ["Average ROE", safe_pct(stats["avg_roe"]), "Average ROCE", safe_pct(stats["avg_roce"])],
        ["Average OPM", safe_pct(stats["avg_opm"]), "Average Revenue CAGR", safe_pct(stats["avg_revenue_growth"])],
        ["Average PAT CAGR", safe_pct(stats["avg_pat_growth"]), "Average Debt/Equity", safe_num(stats["avg_debt_equity"], 2)],
        ["Positive FCF Companies", f'{stats["positive_fcf"]}/{stats["company_count"]}', "", ""],
    ]
    story.append(build_table(summary_data, [42*mm, 30*mm, 52*mm, 32*mm]))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("Company Overview", styles["Section"]))
    company_rows = [["Company", "Name", "Sub-sector", "Weight", "ROE", "ROCE", "OPM", "Revenue CAGR"]]
    for _, row in df.sort_values("index_weight_pct", ascending=False, na_position="last").iterrows():
        company_rows.append([
            clean_text(row.get("company_id")),
            clean_text(row.get("company_name"), "Unknown")[:34],
            clean_text(row.get("sub_sector"))[:28],
            safe_pct(row.get("index_weight_pct")),
            safe_pct(row.get("latest_roe_pct", row.get("roe_percentage"))),
            safe_pct(row.get("roce_percentage")),
            safe_pct(row.get("latest_opm_pct")),
            safe_pct(row.get("revenue_cagr_5yr")),
        ])
    story.append(build_table(company_rows, [24*mm, 57*mm, 42*mm, 24*mm, 22*mm, 22*mm, 22*mm, 30*mm]))
    story.append(PageBreak())
    story.append(Paragraph("Top Company Rankings", styles["Section"]))
    ranking_specs = [
        ("latest_roe_pct", "Top ROE Companies"),
        ("roce_percentage", "Top ROCE Companies"),
        ("revenue_cagr_5yr", "Top Revenue Growth Companies"),
        ("pat_cagr_5yr", "Top PAT Growth Companies"),
        ("latest_fcf_cr", "Top Free Cash Flow Companies"),
    ]
    for metric, title in ranking_specs:
        ranking = top_metric(df, metric, 5)
        if ranking.empty:
            continue
        rows = [["Rank", "Company", "Name", "Sub-sector", "Value"]]
        for rank, (_, row) in enumerate(ranking.iterrows(), 1):
            formatted = safe_pct(row[metric]) if metric != "latest_fcf_cr" else safe_num(row[metric], 1)
            rows.append([str(rank), clean_text(row.get("company_id")), clean_text(row.get("company_name"))[:38], clean_text(row.get("sub_sector"))[:30], formatted])
        story.append(Paragraph(title, styles["Heading3"]))
        story.append(build_table(rows, [18*mm, 30*mm, 75*mm, 55*mm, 30*mm]))
        story.append(Spacer(1, 4*mm))
    story.append(PageBreak())
    story.append(Paragraph("Common Sector Strengths and Risks", styles["Section"]))
    strengths = common_points(df, "pros", 7)
    risks = common_points(df, "cons", 7)
    strength_rows = [["Common Strength", "Frequency"]] + ([[text.capitalize(), str(count)] for text, count in strengths] or [["No recurring strengths detected", "0"]])
    risk_rows = [["Common Risk", "Frequency"]] + ([[text.capitalize(), str(count)] for text, count in risks] or [["No recurring risks detected", "0"]])
    side_table = Table([[build_table(strength_rows, [95*mm, 25*mm]), build_table(risk_rows, [95*mm, 25*mm])]], colWidths=[130*mm, 130*mm])
    side_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(side_table)
    story.append(Spacer(1, 6*mm))
    if "cfo_quality_label" in df.columns:
        story.append(Paragraph("Cash-Flow Quality Distribution", styles["Section"]))
        counts = df["cfo_quality_label"].fillna("Unknown").astype(str).value_counts()
        rows = [["CFO Quality", "Companies"]] + [[label, str(count)] for label, count in counts.items()]
        story.append(build_table(rows, [70*mm, 35*mm]))
    if "capital_allocation_pattern" in df.columns:
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("Capital Allocation Patterns", styles["Section"]))
        counts = df["capital_allocation_pattern"].fillna("Unknown").astype(str).value_counts()
        rows = [["Capital Allocation Pattern", "Companies"]] + [[label, str(count)] for label, count in counts.items()]
        story.append(build_table(rows, [100*mm, 35*mm]))
    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    create_sector_chart(df, sector)
    return output_path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate sector-level financial intelligence PDF reports.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sector", type=str, help="Generate one sector report.")
    group.add_argument("--all", action="store_true", help="Generate reports for all sectors.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of sectors when using --all.")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    data = load_data()
    sectors = available_sectors(data)
    print("\nSPRINT 5 - DAY 34 - SECTOR PDF REPORTS")
    print("=" * 55)
    print(f"Detected sectors : {len(sectors)}")
    print(f"Output directory : {REPORT_DIR}")
    if args.sector:
        matched = next((s for s in sectors if s.lower() == args.sector.strip().lower()), None)
        if not matched:
            print("\nSector not found. Available sectors:")
            for sector in sectors:
                print(f"  - {sector}")
            raise SystemExit(1)
        selected = [matched]
    else:
        selected = sectors[:args.limit] if args.limit else sectors
    success = 0
    failures: list[tuple[str, str]] = []
    for index, sector in enumerate(selected, 1):
        try:
            path = generate_sector_pdf(sector, data)
            success += 1
            print(f"[{index}/{len(selected)}] Created: {path.name}")
        except Exception as error:
            failures.append((sector, str(error)))
            print(f"[{index}/{len(selected)}] Failed: {sector} -> {error}")
    print("\nGeneration summary")
    print(f"Successful : {success}")
    print(f"Failed     : {len(failures)}")
    if failures:
        print("\nFailures:")
        for sector, error in failures:
            print(f"  - {sector}: {error}")

if __name__ == "__main__":
    main()