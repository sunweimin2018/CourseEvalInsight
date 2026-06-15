import pandas as pd
import numpy as np


def clean_and_fuse(parsed_data):
    all_dfs = []
    total_before = 0
    for file_name, sheets in parsed_data.items():
        for sheet_name, content in sheets.items():
            df = pd.DataFrame(content['rows'], columns=content['headers'])
            total_before += len(df)
            all_dfs.append(df)

    if not all_dfs:
        return {'headers': [], 'rows': []}, {
            'total_rows_before': 0, 'total_rows_after': 0,
            'removed_duplicates': 0, 'removed_outliers': 0,
        }

    fused = pd.concat(all_dfs, ignore_index=True)

    # Deduplicate
    before_dedup = len(fused)
    fused = fused.drop_duplicates()
    removed_duplicates = before_dedup - len(fused)

    # Fill nulls: text → ""，numeric → 0
    for col in fused.columns:
        if fused[col].dtype == object:
            fused[col] = fused[col].fillna('')
        else:
            fused[col] = fused[col].fillna(0)

    # Remove outliers (IQR method on numeric columns)
    removed_outliers = 0
    numeric_cols = fused.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        q1 = fused[col].quantile(0.25)
        q3 = fused[col].quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            before = len(fused)
            fused = fused[(fused[col] >= lower) & (fused[col] <= upper)]
            removed_outliers += before - len(fused)

    # Convert back to dict format
    headers = list(fused.columns)
    rows = fused.where(pd.notnull(fused), None).to_dict(orient='records')

    summary = {
        'total_rows_before': total_before,
        'total_rows_after': len(fused),
        'removed_duplicates': removed_duplicates,
        'removed_outliers': removed_outliers,
    }

    return {'headers': headers, 'rows': rows}, summary
