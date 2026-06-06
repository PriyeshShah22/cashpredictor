from __future__ import annotations

from datetime import timedelta

import pandas as pd


EXCLUDED = {'Income', 'Transfer'}


def normalize_description(value: str) -> str:
    text = str(value or '').lower()
    for token in ['upi', 'ref', 'txn', 'debit', 'credit', 'purchase']:
        text = text.replace(token, ' ')
    text = ''.join(ch if ch.isalpha() or ch.isspace() else ' ' for ch in text)
    return ' '.join(text.split())[:24]


def detect_recurring_transactions(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    data = data[(data['amount'] < 0) & (~data['category'].isin(EXCLUDED))].copy()
    if data.empty:
        return []
    data['merchant_key'] = data['description'].apply(normalize_description)
    data['amount_bucket'] = data['amount'].abs().round(-1)

    recurring = []
    for _, group in data.groupby(['merchant_key', 'amount_bucket']):
        group = group.sort_values('date')
        if len(group) < 3:
            continue
        intervals = group['date'].diff().dropna().dt.days
        if intervals.empty:
            continue
        median_gap = intervals.median()
        if 25 <= median_gap <= 35:
            next_date = group['date'].iloc[-1] + timedelta(days=int(round(median_gap)))
            annual_cost = round(float(group['amount'].abs().mean() * 12), 2)
            row = group.iloc[-1]
            recurring.append({
                'merchant': str(row['description']).title(),
                'frequency': 'Monthly',
                'next_expected_date': next_date.strftime('%Y-%m-%d'),
                'annual_cost': annual_cost,
                'amount': round(float(group['amount'].abs().mean()), 2),
                'bank': row['bank'],
            })
    recurring.sort(key=lambda item: item['annual_cost'], reverse=True)
    return recurring[:10]
