from __future__ import annotations

from hashlib import md5

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest


EXCLUDE_CATEGORIES = {'Income', 'Transfer', 'Rent', 'EMI', 'Investment'}


def detect_anomalies(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    debits = data[(data['amount'] < 0) & (~data['category'].isin(EXCLUDE_CATEGORIES))].copy()
    if debits.empty:
        return []

    results = []
    for category, group in debits.groupby('category'):
        if len(group) < 3:
            continue
        z = np.abs(stats.zscore(group['amount'].abs()))
        z = np.nan_to_num(z)
        flagged = group[z > 2.2].copy()
        if flagged.empty:
            continue
        flagged['z_score'] = z[z > 2.2]
        flagged['method'] = 'zscore'
        results.append(flagged)

    if len(debits) >= 10:
        features = pd.DataFrame({
            'amount_abs': debits['amount'].abs(),
            'day_of_week': debits['date'].dt.dayofweek,
            'is_weekend': debits['date'].dt.dayofweek.isin([5, 6]).astype(int),
        })
        iso = IsolationForest(contamination=0.06, random_state=42)
        debits['iso_pred'] = iso.fit_predict(features)
        iso_rows = debits[debits['iso_pred'] == -1].copy()
        iso_rows['method'] = 'isolation_forest'
        iso_rows['z_score'] = 0.0
        if not iso_rows.empty:
            results.append(iso_rows)

    if not results:
        return []

    all_anomalies = pd.concat(results).drop_duplicates(subset=['date', 'description', 'amount', 'bank'])
    output = []
    for _, row in all_anomalies.iterrows():
        cat_group = debits[debits['category'] == row.get('category', 'Others')]
        cat_avg = float(cat_group['amount'].abs().mean()) if len(cat_group) else 0
        multiplier = round(float(abs(row['amount']) / cat_avg), 1) if cat_avg else 0
        severity = 'HIGH' if multiplier >= 3 or abs(row.get('z_score', 0)) >= 3 else 'MEDIUM'
        anomaly_id = md5(f"{row['date']}-{row['bank']}-{row['description']}-{row['amount']}".encode()).hexdigest()[:12]
        output.append({
            'id': anomaly_id,
            'date': pd.to_datetime(row['date']).strftime('%Y-%m-%d'),
            'bank': row.get('bank', ''),
            'description': row['description'],
            'amount': round(float(abs(row['amount'])), 2),
            'category': row.get('category', 'Others'),
            'z_score': round(float(row.get('z_score', 0)), 2),
            'severity': severity,
            'message': f"{multiplier}x above your average {str(row.get('category', 'spend')).lower()} spend" if multiplier else 'Unusual compared with your typical spending pattern',
        })
    return sorted(output, key=lambda x: (x['severity'] == 'HIGH', x['amount']), reverse=True)[:12]
