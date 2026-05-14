"""把 21 个 Sheet 写出为单个 .xlsx，并在 Sheet 名前缀加序号。"""

from __future__ import annotations
from pathlib import Path
import pandas as pd


def write_xlsx(sheets: dict[str, pd.DataFrame], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        for name, df in sheets.items():
            # openpyxl 限制 sheet 名 ≤31 字符
            safe = name[:31]
            df.to_excel(w, sheet_name=safe, index=False)
    return out_path
