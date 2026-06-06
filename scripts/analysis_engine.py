from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from models.anomaly_detector import detect_anomalies
from models.cashout_predictor import forecast_balance
from models.health_scorer import calculate_health_score
from models.insurance_advisor import analyze_insurance_protection
from models.investment_advisor import build_investment_plan
from models.recommendation_engine import generate_recommendations
from models.recurring_detector import detect_recurring_transactions
from scripts.generate_dataset import ensure_demo_dataset
from utils.trend_alerts import evaluate_and_notify_trends


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def _format_currency(value: float) -> float:
    return round(float(value), 2)


def load_dataset(base_dir: Path, dataset_path: Path | None = None) -> pd.DataFrame:
    dataset = dataset_path if dataset_path else base_dir / 'data' / 'processed' / 'final_dataset.csv'
    if not dataset.exists():
        ensure_demo_dataset(base_dir)
        dataset = base_dir / 'data' / 'processed' / 'final_dataset.csv'
    df = pd.read_csv(dataset)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['date', 'bank']).reset_index(drop=True)
    return df


def _monthly_surplus(data: pd.DataFrame) -> float:
    monthly = data.groupby(data['date'].dt.to_period('M'))['amount'].sum()
    if monthly.empty:
        return 0.0
    return float(monthly.tail(3).mean())


def _summary_metrics(data: pd.DataFrame) -> dict:
    expenses = data[(data['amount'] < 0) & (data['type'] != 'Transfer')]
    income = data[data['amount'] > 0]
    current_balance = float(data.sort_values('date').groupby('bank')['bank_balance'].last().sum())
    total_income = float(income['amount'].sum())
    total_spending = float(expenses['amount'].abs().sum())
    active_days = max(1, (data['date'].max() - data['date'].min()).days + 1)
    daily_burn_rate = total_spending / active_days
    monthly_surplus = _monthly_surplus(data)
    return {
        'current_balance': _format_currency(current_balance),
        'total_income': _format_currency(total_income),
        'total_spending': _format_currency(total_spending),
        'daily_burn_rate': _format_currency(daily_burn_rate),
        'monthly_surplus': _format_currency(monthly_surplus),
    }


def _status_from_days(days_remaining: int) -> str:
    if days_remaining < 7:
        return 'CRITICAL'
    if days_remaining <= 30:
        return 'WARNING'
    return 'SAFE'


def _weekly_spending(data: pd.DataFrame) -> dict:
    expenses = data[data['amount'] < 0].copy()
    if expenses.empty:
        return {'labels': [], 'values': []}
    expenses['week'] = expenses['date'].dt.to_period('W').astype(str)
    grouped = expenses.groupby('week')['amount'].sum().abs().tail(4)
    labels = [f'Week {i + 1}' for i in range(len(grouped))]
    return {'labels': labels, 'values': [round(float(v), 2) for v in grouped.values]}


def _spending_by_category(data: pd.DataFrame) -> dict:
    expenses = data[(data['amount'] < 0) & (~data['category'].isin(['Transfer', 'Income']))]
    grouped = expenses.groupby('category')['amount'].sum().abs().sort_values(ascending=False)
    return {str(k): round(float(v), 2) for k, v in grouped.items()}


def _top_leaks(spending_by_category: dict) -> list[dict]:
    total = sum(spending_by_category.values()) or 1
    output = []
    for category, amount in sorted(spending_by_category.items(), key=lambda item: item[1], reverse=True)[:6]:
        output.append({
            'category': category,
            'amount': round(float(amount), 2),
            'percent_of_spending': round(float(amount / total * 100), 1),
        })
    return output


def _bank_balances(full_df: pd.DataFrame) -> dict:
    latest = full_df.sort_values('date').groupby('bank')['bank_balance'].last()
    return {str(bank): round(float(balance), 2) for bank, balance in latest.items()}


def _comparison_deltas(data: pd.DataFrame) -> dict:
    latest_end = data['date'].max()
    latest_start = latest_end - pd.Timedelta(days=29)
    prev_end = latest_start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=29)
    latest = data[(data['date'] >= latest_start) & (data['date'] <= latest_end)]
    previous = data[(data['date'] >= prev_start) & (data['date'] <= prev_end)]

    def metric(frame, kind):
        if kind == 'balance':
            if frame.empty:
                return 0
            return frame.sort_values('date').groupby('bank')['bank_balance'].last().sum()
        if kind == 'income':
            return frame[frame['amount'] > 0]['amount'].sum()
        if kind == 'spending':
            return frame[frame['amount'] < 0]['amount'].abs().sum()
        return frame[frame['amount'] < 0]['amount'].abs().sum() / max(1, len(frame['date'].dt.date.unique()))

    deltas = {}
    for key, kind in [('current_balance', 'balance'), ('total_income', 'income'), ('total_spending', 'spending'), ('daily_burn_rate', 'burn')]:
        curr = metric(latest, kind)
        prev = metric(previous, kind)
        change = ((curr - prev) / prev * 100) if prev else 0
        deltas[key] = round(float(change), 1)
    return deltas


def _serialize_transactions(data: pd.DataFrame, anomalies: list[dict]) -> list[dict]:
    anomaly_ids = {(a['date'], a['bank'], a['description'], round(float(a['amount']), 2)) for a in anomalies}
    output = []
    for row in data.sort_values('date', ascending=False).itertuples(index=False):
        output.append({
            'date': row.date.strftime('%Y-%m-%d'),
            'bank': row.bank,
            'description': row.description,
            'category': row.category,
            'amount': round(float(row.amount), 2),
            'balance': round(float(row.bank_balance), 2),
            'is_anomaly': (row.date.strftime('%Y-%m-%d'), row.bank, row.description, round(abs(float(row.amount)), 2)) in anomaly_ids,
        })
    return output


def _goal_progress(summary: dict, base_dir: Path, goals_path: Path | None = None) -> list[dict]:
    goals_path = goals_path if goals_path else base_dir / 'data' / 'processed' / 'goals.json'
    goals = _read_json(goals_path, [])
    current = float(summary.get('current_balance', 0) or 0)
    monthly_surplus = max(float(summary.get('monthly_surplus', 0) or 0), 1)
    output = []
    for goal in goals:
        target = float(goal.get('target', 0) or 0)
        progress = min(100, (current / target) * 100) if target else 0
        remaining = max(target - current, 0)
        months_to_goal = int(np.ceil(remaining / monthly_surplus)) if remaining > 0 else 0
        output.append({
            'name': goal.get('name'),
            'target': round(target, 2),
            'deadline': goal.get('deadline'),
            'progress': round(progress, 1),
            'eta_months': months_to_goal,
        })
    return output


def run_analysis(
    base_dir: Path | str,
    bank: str | None = None,
    dataset_path: Path | None = None,
    user_files: dict | None = None,
    alert_email: str | None = None,
    user_name: str | None = None,
) -> dict:
    root = Path(base_dir)
    full_df = load_dataset(root, dataset_path=dataset_path)
    
    meta_path = user_files['metadata'] if user_files else root / 'data' / 'processed' / 'source_metadata.json'
    source_meta = _read_json(meta_path, {'mode': 'demo'})

    filtered = full_df.copy()
    if bank and bank.lower() != 'all':
        filtered = filtered[filtered['bank'].str.lower() == bank.lower()].copy()
        if filtered.empty:
            filtered = full_df.copy()

    summary = _summary_metrics(filtered)
    forecast = forecast_balance(filtered)
    summary['days_remaining'] = int(forecast['cashout_days'])
    summary['cashout_date'] = forecast['cashout_date']
    summary['status'] = _status_from_days(summary['days_remaining'])
    summary['comparison_deltas'] = _comparison_deltas(filtered)

    spending_by_category = _spending_by_category(filtered)
    anomalies = detect_anomalies(filtered)
    dismissed_path = user_files['dismissed'] if user_files else root / 'data' / 'processed' / 'dismissed_anomalies.json'
    dismissed_ids = set(_read_json(dismissed_path, []))
    anomalies = [item for item in anomalies if item['id'] not in dismissed_ids]
    health_score = calculate_health_score(filtered, summary, anomalies)
    recommendations = generate_recommendations(filtered, spending_by_category, summary)
    investments = build_investment_plan(summary, spending_by_category, filtered)
    recurring = detect_recurring_transactions(filtered)
    insurance_output = analyze_insurance_protection(full_df)
    transactions = _serialize_transactions(filtered, anomalies)
    autonomous_alert = evaluate_and_notify_trends(
        full_df,
        alert_email=alert_email,
        alert_state_path=user_files['alerts'] if user_files else root / 'data' / 'processed' / 'alert_state.json',
        user_name=user_name,
    )

    dow = filtered[filtered['amount'] < 0].groupby(filtered['date'].dt.day_name())['amount'].sum().abs()
    ordered_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_profile = {day: round(float(dow.get(day, 0)), 2) for day in ordered_days}
    peak_day = max(day_profile, key=day_profile.get) if day_profile else 'Saturday'

    net_months = filtered.groupby(filtered['date'].dt.to_period('M'))['amount'].sum().tail(12)
    net_score = [
        {'month': str(period), 'net': round(float(value), 2), 'positive': bool(value >= 0)}
        for period, value in net_months.items()
    ]

    result = {
        'summary': summary,
        'health_score': health_score,
        'forecast': forecast,
        'spending_by_category': spending_by_category,
        'weekly_spending': _weekly_spending(filtered),
        'top_leaks': _top_leaks(spending_by_category),
        'anomalies': anomalies,
        'recommendations': recommendations,
        'investments': investments,
        'transactions': transactions,
        'bank_balances': _bank_balances(full_df),
        'connected_banks': sorted(full_df['bank'].unique().tolist()),
        'recurring_bills': recurring,
        'insurance_insights': insurance_output,
        'goals': _goal_progress(summary, root, goals_path=user_files['goals'] if user_files else None),
        'day_of_week_profile': {
            'peak_day': peak_day,
            'average_peak_spend': day_profile.get(peak_day, 0),
            'series': day_profile,
        },
        'net_score': net_score,
        'autonomous_alert': autonomous_alert,
        'demo_mode': source_meta.get('mode', 'demo') == 'demo',
    }
    return result
