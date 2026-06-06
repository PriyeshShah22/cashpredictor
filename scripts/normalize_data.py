from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from models.category_classifier import assign_categories
from scripts.pdf_to_csv import convert_pdf_to_csv


BANK_SCHEMAS = {
    'HDFC': {
        'date': 'Date',
        'description': 'Narration',
        'debit': 'Withdrawal Amt.',
        'credit': 'Deposit Amt.',
        'balance': 'Closing Balance',
    },
    'SBI': {
        'date': 'Txn Date',
        'description': 'Description',
        'debit': 'Debit',
        'credit': 'Credit',
        'balance': 'Balance',
    },
    'ICICI': {
        'date': 'Transaction Date',
        'description': 'Transaction Remarks',
        'debit': 'Debit Amount',
        'credit': 'Credit Amount',
        'balance': 'Available Balance',
    },
    'AXIS': {
        'date': 'Tran Date',
        'description': 'Particulars',
        'debit': 'Debit',
        'credit': 'Credit',
        'balance': 'Balance',
    },
}


def parse_amount(value) -> float:
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace('₹', '').replace(',', '').strip()
    if text in {'', '-', 'nan', 'None'}:
        return 0.0
    text = text.replace('CR', '').replace('DR', '')
    try:
        return float(text)
    except ValueError:
        return 0.0


def detect_bank_from_headers(headers: Iterable[str]) -> str:
    header_set = {str(item).strip() for item in headers}
    for bank, schema in BANK_SCHEMAS.items():
        required = {schema['date'], schema['description'], schema['balance']}
        if required.issubset(header_set):
            return bank
    return 'Other'


def _standardize(df: pd.DataFrame, bank: str) -> pd.DataFrame:
    schema = BANK_SCHEMAS.get(bank)
    if schema is None:
        lower_map = {col.lower(): col for col in df.columns}
        possible = ['date', 'description', 'amount', 'bank_balance']
        if all(col in lower_map for col in possible):
            out = df.rename(columns={lower_map['bank_balance']: 'bank_balance', lower_map['description']: 'description', lower_map['date']: 'date', lower_map['amount']: 'amount'}).copy()
            if 'bank' not in out.columns:
                out['bank'] = bank
            return out[['date', 'bank', 'description', 'amount', 'bank_balance']]
        raise ValueError(f'Unsupported schema for bank {bank}')

    out = pd.DataFrame()
    out['date'] = pd.to_datetime(df[schema['date']], dayfirst=True, errors='coerce')
    out['description'] = df[schema['description']].fillna('').astype(str).str.strip()
    out['debit'] = df.get(schema['debit'], 0).apply(parse_amount)
    out['credit'] = df.get(schema['credit'], 0).apply(parse_amount)
    out['amount'] = out['credit'] - out['debit']
    out['bank_balance'] = df.get(schema['balance'], 0).apply(parse_amount)
    out['bank'] = bank
    out = out.dropna(subset=['date'])
    return out[['date', 'bank', 'description', 'amount', 'bank_balance']]


def normalize_file(path: str, bank_hint: str | None = None) -> pd.DataFrame:
    file_path = Path(path)
    if file_path.suffix.lower() == '.pdf':
        csv_path = convert_pdf_to_csv(str(file_path))
        file_path = Path(csv_path)

    try:
        df = pd.read_csv(file_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=['date', 'bank', 'description', 'amount', 'bank_balance', 'category', 'type'])

    bank = (bank_hint or '').strip().upper() or detect_bank_from_headers(df.columns)
    normalized = _standardize(df, bank)
    normalized = normalized.sort_values(['date', 'description', 'amount']).reset_index(drop=True)
    normalized = assign_categories(normalized)
    return normalized[['date', 'bank', 'description', 'amount', 'bank_balance', 'category', 'type']]


def deduplicate_transactions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    deduped = df.copy()
    deduped['dedupe_key'] = (
        deduped['date'].dt.strftime('%Y-%m-%d') + '|' +
        deduped['description'].str.lower().str.slice(0, 18) + '|' +
        deduped['amount'].round(2).astype(str) + '|' +
        deduped['bank']
    )
    deduped = deduped.drop_duplicates(subset=['dedupe_key']).drop(columns=['dedupe_key'])
    return deduped


def normalize_multiple(paths: list[str], bank_hints: list[str] | None = None, output_path: str | Path | None = None) -> pd.DataFrame:
    frames = []
    hints = bank_hints or [''] * len(paths)
    for idx, path in enumerate(paths):
        frame = normalize_file(path, bank_hint=hints[idx] if idx < len(hints) else None)
        frames.append(frame)
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=['date', 'bank', 'description', 'amount', 'bank_balance', 'category', 'type'])
    if not merged.empty:
        merged['date'] = pd.to_datetime(merged['date'])
        merged = merged.sort_values(['date', 'bank']).reset_index(drop=True)
        merged = deduplicate_transactions(merged)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(output_path, index=False)
    return merged
