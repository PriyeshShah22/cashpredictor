from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_health_score(df: pd.DataFrame, summary: dict, anomalies: list[dict]) -> dict:
    income = float(summary.get('total_income', 1) or 1)
    spend = float(summary.get('total_spending', 0) or 0)

    spending_control = max(0, min(100, (1 - spend / income) * 150)) if income else 0
    savings_ratio = max(0, min(100, ((income - spend) / income) * 200)) if income else 0

    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    bills = data[data['category'].isin(['Rent', 'EMI', 'Subscriptions', 'Utilities'])].copy()
    if not bills.empty:
        monthly_bills = bills.groupby(bills['date'].dt.to_period('M'))['amount'].sum().abs()
        bill_std = monthly_bills.std() if len(monthly_bills) > 1 else 0
        bill_regularity = max(0, min(100, 100 - (bill_std / (monthly_bills.mean() + 1)) * 50))
    else:
        bill_regularity = 72

    high_severity = len([item for item in anomalies if item.get('severity') == 'HIGH'])
    anomaly_score = max(0, 100 - high_severity * 15)

    daily_balance = data.groupby('date')['bank_balance'].last()
    if len(daily_balance) > 7:
        recent = daily_balance.iloc[-7:].values
        slope = np.polyfit(range(len(recent)), recent, 1)[0]
        balance_trend = min(100, max(0, 50 + slope * 0.01))
    else:
        balance_trend = 50

    overall = (
        spending_control * 0.30 +
        savings_ratio * 0.25 +
        bill_regularity * 0.20 +
        anomaly_score * 0.15 +
        balance_trend * 0.10
    )

    return {
        'overall': round(overall),
        'spending_control': round(spending_control),
        'savings_habit': round(savings_ratio),
        'bill_regularity': round(bill_regularity),
        'anomaly_score': round(anomaly_score),
        'balance_trend': round(balance_trend),
    }
