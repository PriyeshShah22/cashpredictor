from __future__ import annotations

from pathlib import Path

import pandas as pd
import pdfplumber


def convert_pdf_to_csv(pdf_path: str, output_path: str | None = None) -> str:
    pdf_path = str(pdf_path)
    target = output_path or str(Path(pdf_path).with_suffix('.csv'))
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table and len(table) > 1:
                headers = [str(cell or '').strip() for cell in table[0]]
                for raw in table[1:]:
                    if not raw:
                        continue
                    row = {headers[i] if i < len(headers) else f'col_{i}': (raw[i] if i < len(raw) else '') for i in range(len(headers))}
                    rows.append(row)
                continue
            text = page.extract_text() or ''
            for line in text.splitlines():
                parts = [part.strip() for part in line.split('  ') if part.strip()]
                if len(parts) >= 4:
                    rows.append({
                        'Date': parts[0],
                        'Narration': parts[1],
                        'Withdrawal Amt.': parts[2],
                        'Deposit Amt.': parts[3] if len(parts) > 3 else '',
                        'Closing Balance': parts[4] if len(parts) > 4 else '',
                    })
    pd.DataFrame(rows).to_csv(target, index=False)
    return target
