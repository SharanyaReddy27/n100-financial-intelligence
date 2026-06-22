import os
import pandas as pd

RAW_DIR = "data/raw"

CORE_FILES = {
    "companies.xlsx",
    "profitandloss.xlsx",
    "balancesheet.xlsx",
    "cashflow.xlsx",
    "analysis.xlsx",
    "documents.xlsx",
    "prosandcons.xlsx",
}

def load_excel_file(file_name):
    file_path = os.path.join(RAW_DIR, file_name)

    if file_name in CORE_FILES:
        df = pd.read_excel(file_path, header=1)
    else:
        df = pd.read_excel(file_path, header=0)

    df.columns = [str(col).strip() for col in df.columns]

    return df


def preview_all_files():
    for file_name in os.listdir(RAW_DIR):
        if file_name.endswith(".xlsx"):
            df = load_excel_file(file_name)
            output_name = file_name.replace(".xlsx", ".csv")
            output_path = os.path.join("data/processed", output_name)
            df.to_csv(output_path, index=False)
            print("Saved:", output_path)
            print("\n" + "=" * 60)
            print("FILE:", file_name)
            print("ROWS:", df.shape[0])
            print("COLS:", df.shape[1])
            print("COLUMNS:", list(df.columns))
            print(df.head())


if __name__ == "__main__":
    preview_all_files()