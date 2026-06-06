from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.normalize_data import normalize_multiple

RNG = np.random.default_rng(42)
PERSONA = {
    'name': 'Aarav Mehta',
    'city': 'Bengaluru',
    'salary': 98000,
}

BANK_CONFIG = {
    'HDFC': {'starting_balance': 42000, 'salary_account': True},
    'SBI': {'starting_balance': 18000, 'salary_account': False},
    'ICICI': {'starting_balance': 26000, 'salary_account': False},
}


def _month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    return list(pd.date_range(start.normalize().replace(day=1), end.normalize(), freq='MS'))


def _append(txns: list[dict], date, description: str, amount: float):
    txns.append({'date': pd.Timestamp(date), 'description': description, 'amount': round(float(amount), 2)})


def build_bank_transactions(bank: str, start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    txns: list[dict] = []
    months = _month_starts(start, end)

    for month in months:
        if bank == 'HDFC':
            _append(txns, month + pd.Timedelta(days=0), 'SALARY CREDIT ACME TECH', PERSONA['salary'])
            _append(txns, month + pd.Timedelta(days=1), 'IMPS TO SBI HOME', -18000)
            _append(txns, month + pd.Timedelta(days=2), 'IMPS TO ICICI LIFE', -12000)
            _append(txns, month + pd.Timedelta(days=4), 'HOUSE RENT TRANSFER', -22000)
            _append(txns, month + pd.Timedelta(days=7), 'HDFC BANK EMI', -6500)
            _append(txns, month + pd.Timedelta(days=11), 'NETFLIX INDIA', -649)
            _append(txns, month + pd.Timedelta(days=12), 'SPOTIFY PREMIUM', -119)
            _append(txns, month + pd.Timedelta(days=20), 'GOOGLE ONE', -130)
        elif bank == 'SBI':
            _append(txns, month + pd.Timedelta(days=1), 'IMPS FROM HDFC HOME', 18000)
            _append(txns, month + pd.Timedelta(days=9), 'BESCOM ELECTRICITY', -2150)
            _append(txns, month + pd.Timedelta(days=13), 'AIRTEL BROADBAND', -1199)
            _append(txns, month + pd.Timedelta(days=16), 'PNG GAS BILL', -860)
            _append(txns, month + pd.Timedelta(days=24), 'UPI TO PARENTS', -5000)
        elif bank == 'ICICI':
            _append(txns, month + pd.Timedelta(days=2), 'IMPS FROM HDFC LIFE', 12000)
            _append(txns, month + pd.Timedelta(days=10), 'GROWW SIP EQUITY', -5000)
            _append(txns, month + pd.Timedelta(days=18), 'DIGITAL GOLD PURCHASE', -1200)
            _append(txns, month + pd.Timedelta(days=25), 'AMAZON PRIME', -299)

    current = start
    while current <= end:
        day = current.dayofweek
        if bank == 'HDFC':
            if RNG.random() < 0.65:
                _append(txns, current, RNG.choice(['SWIGGY', 'ZOMATO', 'BLINKIT MART', 'STARBUCKS INDIA']), -RNG.integers(180, 1100))
            if RNG.random() < 0.20:
                _append(txns, current, RNG.choice(['OLA RIDES', 'UBER TRIP', 'FASTAG RECHARGE']), -RNG.integers(120, 700))
        elif bank == 'SBI':
            if RNG.random() < 0.45:
                _append(txns, current, RNG.choice(['RELIANCE FRESH', 'BIGBASKET', 'DMART READY']), -RNG.integers(250, 2200))
            if day >= 5 and RNG.random() < 0.25:
                _append(txns, current, RNG.choice(['BOOKMYSHOW', 'PVR CINEMAS', 'INOX MOVIES']), -RNG.integers(300, 1600))
        elif bank == 'ICICI':
            if RNG.random() < 0.35:
                _append(txns, current, RNG.choice(['AMAZON PAY', 'FLIPKART', 'MYNTRA', 'AJIO']), -RNG.integers(450, 3800))
            if RNG.random() < 0.18:
                _append(txns, current, RNG.choice(['APOLLO PHARMACY', 'MEDPLUS', 'URBANCLAP']), -RNG.integers(250, 1800))
        if day >= 5 and RNG.random() < 0.15:
            _append(txns, current, 'ATM CASH WITHDRAWAL', -RNG.integers(500, 4000))
        current += pd.Timedelta(days=1)

    # Inject anomalies and duplicate charges
    if bank == 'ICICI':
        _append(txns, end - pd.Timedelta(days=18), 'AMAZON PAY', -14250)
    if bank == 'HDFC':
        duplicate_day = end - pd.Timedelta(days=11)
        _append(txns, duplicate_day, 'BLINKIT MART', -799)
        _append(txns, duplicate_day, 'BLINKIT MART', -799)

    txns.sort(key=lambda x: (x['date'], x['description'], x['amount']))
    return txns


def to_raw_schema(bank: str, txns: list[dict], output_dir: Path) -> Path:
    balance = BANK_CONFIG[bank]['starting_balance']
    rows = []
    for txn in txns:
        balance += txn['amount']
        debit = abs(txn['amount']) if txn['amount'] < 0 else 0
        credit = txn['amount'] if txn['amount'] > 0 else 0
        if bank == 'HDFC':
            rows.append({
                'Date': txn['date'].strftime('%d/%m/%Y'),
                'Narration': txn['description'],
                'Withdrawal Amt.': debit,
                'Deposit Amt.': credit,
                'Closing Balance': round(balance, 2),
            })
        elif bank == 'SBI':
            rows.append({
                'Txn Date': txn['date'].strftime('%d/%m/%Y'),
                'Description': txn['description'],
                'Debit': debit,
                'Credit': credit,
                'Balance': round(balance, 2),
            })
        else:
            rows.append({
                'Transaction Date': txn['date'].strftime('%d/%m/%Y'),
                'Transaction Remarks': txn['description'],
                'Debit Amount': debit,
                'Credit Amount': credit,
                'Available Balance': round(balance, 2),
            })
    df = pd.DataFrame(rows)
    path = output_dir / f'{bank.lower()}_statement.csv'
    df.to_csv(path, index=False)
    return path


def generate_demo_dataset(base_dir: Path | str | None = None) -> Path:
    root = Path(base_dir or Path(__file__).resolve().parents[1])
    raw_dir = root / 'data' / 'raw'
    processed_dir = root / 'data' / 'processed'
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    start = pd.Timestamp('2025-10-01')
    end = pd.Timestamp('2026-04-20')
    raw_files = []
    for bank in BANK_CONFIG:
        txns = build_bank_transactions(bank, start, end)
        raw_files.append(str(to_raw_schema(bank, txns, raw_dir)))

    final_dataset = processed_dir / 'final_dataset.csv'
    normalize_multiple(raw_files, bank_hints=list(BANK_CONFIG.keys()), output_path=final_dataset)
    (processed_dir / 'source_metadata.json').write_text(json.dumps({'mode': 'demo'}, indent=2), encoding='utf-8')
    return final_dataset


def ensure_demo_dataset(base_dir: Path | str | None = None) -> Path:
    root = Path(base_dir or Path(__file__).resolve().parents[1])
    final_dataset = root / 'data' / 'processed' / 'final_dataset.csv'
    if final_dataset.exists() and final_dataset.stat().st_size > 0:
        return final_dataset
    return generate_demo_dataset(root)


if __name__ == '__main__':
    path = generate_demo_dataset(Path(__file__).resolve().parents[1])
    print(path)
