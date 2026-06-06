from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from utils.email_service import send_email


DEFAULT_SUGGESTION = 'Review the dashboard and reduce discretionary spending before the next billing cycle.'
CATEGORY_SUGGESTIONS = {
    'Food': 'Reduce impulse food delivery orders and set a weekly dining limit.',
    'Shopping': 'Pause non-essential purchases and compare with your monthly budget.',
    'Subscriptions': 'Audit recurring subscriptions and cancel or downgrade unused plans.',
    'Utilities': 'Review plan changes and look for cheaper broadband, mobile, or electricity options.',
    'Transport': 'Consolidate commute or ride-hailing usage where possible.',
}


def check_increasing_trend(data: list[float] | tuple[float, ...]) -> bool:
    values = [float(value) for value in data if value is not None]
    if len(values) < 3:
        return False
    if len(values) > 5:
        values = values[-5:]
    return all(values[idx] < values[idx + 1] for idx in range(len(values) - 1))



def _safe_float(value: float) -> float:
    return round(float(value), 2)



def _build_alert(scope: str, label: str, periods: list[str], values: list[float]) -> dict:
    baseline = values[0]
    previous_average = sum(values[:-1]) / max(1, len(values) - 1)
    latest_value = values[-1]
    percentage_increase = ((latest_value - baseline) / baseline * 100) if baseline else 0.0
    estimated_monthly_impact = max(0.0, latest_value - previous_average)
    suggestion = CATEGORY_SUGGESTIONS.get(label, DEFAULT_SUGGESTION)
    alert_key = f"{scope}:{label}:{'|'.join(periods)}:{'|'.join(f'{v:.2f}' for v in values)}"

    return {
        'scope': scope,
        'label': label,
        'periods': periods,
        'recent_values': [_safe_float(value) for value in values],
        'percentage_increase': _safe_float(percentage_increase),
        'estimated_monthly_impact': _safe_float(estimated_monthly_impact),
        'suggested_action': suggestion,
        'alert_key': alert_key,
    }



def generate_spending_alerts(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    expenses = data[(data['amount'] < 0) & (data.get('type', 'Expense') != 'Transfer')].copy()
    if expenses.empty:
        return []

    expenses['month'] = expenses['date'].dt.to_period('M')
    alerts: list[dict] = []

    total_monthly = expenses.groupby('month')['amount'].sum().abs().sort_index()
    total_values = total_monthly.tail(3).tolist()
    total_periods = total_monthly.tail(3).index.astype(str).tolist()
    if len(total_values) >= 3 and check_increasing_trend(total_values):
        alerts.append(_build_alert('overall', 'Total spending', total_periods, total_values))

    category_monthly = (
        expenses.groupby(['month', 'category'])['amount']
        .sum()
        .abs()
        .reset_index(name='spend')
        .sort_values('month')
    )
    for category, group in category_monthly.groupby('category'):
        group = group[group['spend'] > 0].sort_values('month')
        values = group['spend'].tail(3).tolist()
        periods = group['month'].tail(3).astype(str).tolist()
        if len(values) >= 3 and check_increasing_trend(values):
            alerts.append(_build_alert('category', str(category), periods, values))

    alerts.sort(
        key=lambda item: (item['estimated_monthly_impact'], item['percentage_increase']),
        reverse=True,
    )
    return alerts[:5]



def _read_alert_state(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}



def _write_alert_state(path: Path | None, payload: dict) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')



def _format_email_message(alert: dict, user_name: str | None = None) -> str:
    greeting = f"Hi {user_name}," if user_name else 'Hi,'
    periods = ', '.join(alert['periods'])
    values = ', '.join(f"₹{value:,.2f}" for value in alert['recent_values'])
    return (
        f"{greeting}\n\n"
        f"CashForecast detected a continuously increasing spending trend in {alert['label'].lower()}.\n\n"
        f"Observed cycles: {periods}\n"
        f"Spending values: {values}\n"
        f"Percentage increase: {alert['percentage_increase']:.2f}%\n"
        f"Estimated monthly impact: ₹{alert['estimated_monthly_impact']:.2f}\n"
        f"Suggested action: {alert['suggested_action']}\n\n"
        "Please review your dashboard for more details and take action early to avoid cash-out risk.\n\n"
        "— CashForecast Autonomous Alert System"
    )



def evaluate_and_notify_trends(
    df: pd.DataFrame,
    alert_email: str | None = None,
    alert_state_path: Path | None = None,
    user_name: str | None = None,
) -> dict:
    alerts = generate_spending_alerts(df)
    if not alerts:
        return {
            'triggered': False,
            'email_status': 'not_triggered',
            'alerts': [],
        }

    top_alert = alerts[0]
    state = _read_alert_state(alert_state_path)
    duplicate_suppressed = state.get('last_alert_key') == top_alert['alert_key']
    email_status = 'suppressed_duplicate'

    if not duplicate_suppressed:
        subject = f"CashForecast Alert: {top_alert['label']} is increasing"
        message = _format_email_message(top_alert, user_name=user_name)
        send_result = send_email(alert_email or '', subject, message)
        email_status = send_result.get('status', 'unknown')
        _write_alert_state(
            alert_state_path,
            {
                'last_alert_key': top_alert['alert_key'],
                'last_email_status': email_status,
                'last_checked_at': datetime.utcnow().isoformat() + 'Z',
                'last_alert': top_alert,
            },
        )

    return {
        'triggered': True,
        'email_status': email_status,
        'duplicate_suppressed': duplicate_suppressed,
        'top_alert': top_alert,
        'alerts': alerts,
    }
