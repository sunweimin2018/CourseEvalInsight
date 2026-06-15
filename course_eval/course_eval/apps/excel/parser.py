import os
import pandas as pd


def parse_excel(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    engine = 'openpyxl' if ext == '.xlsx' else 'xlrd'
    sheets = {}
    xl = pd.ExcelFile(file_path, engine=engine)
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name)
        df = df.where(pd.notnull(df), None)
        sheets[sheet_name] = {
            'headers': list(df.columns.astype(str)),
            'rows': df.to_dict(orient='records'),
        }
    return sheets
