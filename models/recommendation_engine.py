from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans


ARCHETYPE_NAMES = {
    0: 'subscription_heavy',
    1: 'food_delivery_addict',
    2: 'impulse_shopper',
    3: 'balanced_spender',
    4: 'saver',
}

TEMPLATE_CENTROIDS = np.array([
    [3000, 8000, 5000, 3000, 2000],
    [1000, 15000, 4000, 2000, 1500],
    [800, 6000, 18000, 4000, 2500],
    [1200, 8000, 6000, 3000, 3000],
    [500, 4000, 2000, 1000, 1500],
], dtype=float)


def get_user_archetype(spending_by_category: dict) -> str:
    vector = np.array([
        spending_by_category.get('Subscriptions', 0),
        spending_by_category.get('Food', 0),
        spending_by_category.get('Shopping', 0),
        spending_by_category.get('Entertainment', 0),
        spending_by_category.get('Transport', 0),
    ], dtype=float).reshape(1, -1)
    km = KMeans(n_clusters=5, init=TEMPLATE_CENTROIDS, n_init=1, random_state=42)
    km.fit(TEMPLATE_CENTROIDS)
    label = int(km.predict(vector)[0])
    return ARCHETYPE_NAMES.get(label, 'balanced_spender')


def _month_series(df: pd.DataFrame) -> pd.Series:
    monthly = df.groupby(df['date'].dt.to_period('M'))['amount'].sum()
    return monthly


def generate_recommendations(df: pd.DataFrame, spending_by_category: dict, summary: dict) -> list[dict]:
    if df.empty:
        return []
    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    expense_df = data[data['amount'] < 0].copy()
    monthly_expenses = abs(expense_df.groupby(expense_df['date'].dt.to_period('M'))['amount'].sum()).mean() if not expense_df.empty else 0
    archetype = get_user_archetype(spending_by_category or {})
    recommendations: list[dict] = []

    # 1. Subscription audit via recurring monthly charges
    subs = expense_df[expense_df['category'] == 'Subscriptions'].copy()
    if not subs.empty:
        monthly_subs = subs.groupby('description')['amount'].sum().abs().sort_values(ascending=False).head(3)
        for description, amount in monthly_subs.items():
            recommendations.append({
                'type': 'subscription',
                'title': f'Review {description.title()}',
                'description': f'{description.title()} is consuming about ₹{amount:,.0f} across the analyzed period. Consider cancelling or downgrading.',
                'monthly_saving': round(float(amount / max(1, subs['date'].dt.to_period('M').nunique())), 2),
                'priority_score': float(amount),
                'icon': 'tv',
            })

    # 2. Category reduction against user income benchmark
    income = float(summary.get('total_income', 0) or 0)
    benchmark = {
        'Food': 0.15,
        'Shopping': 0.12,
        'Entertainment': 0.08,
        'Transport': 0.08,
        'Subscriptions': 0.03,
    }
    if income > 0:
        for category, share in benchmark.items():
            spent = float(spending_by_category.get(category, 0))
            allowed = income * share
            if spent > allowed * 1.1:
                savings = max(0.0, spent - allowed)
                recommendations.append({
                    'type': 'spending_cut',
                    'title': f'Reduce {category.lower()} spending',
                    'description': f'Your {category.lower()} outflow is above its benchmark band. Trimming it toward ₹{allowed:,.0f} can improve runway.',
                    'monthly_saving': round(savings / max(1, data['date'].dt.to_period('M').nunique()), 2),
                    'priority_score': float(savings),
                    'icon': 'trending-down',
                })

    # 3. Emergency fund alert from months covered
    balance = float(summary.get('current_balance', 0) or 0)
    months_covered = balance / monthly_expenses if monthly_expenses > 0 else math.inf
    if months_covered < 3:
        recommendations.append({
            'type': 'emergency',
            'title': 'Build your emergency fund',
            'description': f'Current balance covers only {months_covered:.1f} months of expenses. Target at least 3–6 months.',
            'monthly_saving': 0,
            'priority_score': 10000 - min(balance, 9999),
            'icon': 'shield',
        })

    # 4. High frequency small spends
    small_food = expense_df[(expense_df['category'] == 'Food') & (expense_df['amount'].abs() < 500)]
    if len(small_food) >= 12:
        avg_small = small_food['amount'].abs().mean()
        recommendations.append({
            'type': 'habit',
            'title': 'Tighten micro-spends',
            'description': f'You made {len(small_food)} small food orders averaging ₹{avg_small:,.0f}. Cutting just 25% of them can free up cash.',
            'monthly_saving': round(float(avg_small * 0.25 * 8), 2),
            'priority_score': float(len(small_food) * avg_small),
            'icon': 'coffee',
        })

    # 5. Duplicate charges within short window
    temp = expense_df.copy()
    temp['desc_key'] = temp['description'].str.lower().str.replace(r'\d+', '', regex=True).str.strip()
    temp['abs_amount'] = temp['amount'].abs().round(2)
    dupe_rows = temp[temp.duplicated(subset=['desc_key', 'abs_amount', 'date'], keep=False)]
    if not dupe_rows.empty:
        common = dupe_rows.iloc[0]
        recommendations.append({
            'type': 'duplicate',
            'title': 'Review possible duplicate charge',
            'description': f"{common['description']} appears multiple times for nearly the same amount on the same day.",
            'monthly_saving': round(float(common['abs_amount']), 2),
            'priority_score': float(common['abs_amount'] * 1.5),
            'icon': 'copy',
        })

    # 6. Weekend overspend
    dow = expense_df.groupby(expense_df['date'].dt.dayofweek)['amount'].sum().abs()
    weekday_avg = dow[dow.index < 5].mean() if any(dow.index < 5) else 0
    weekend_avg = dow[dow.index >= 5].mean() if any(dow.index >= 5) else 0
    if weekday_avg and weekend_avg > weekday_avg * 1.35:
        recommendations.append({
            'type': 'behavior',
            'title': 'Watch weekend overspending',
            'description': f'Weekend spend runs {weekend_avg / max(weekday_avg, 1):.1f}x your weekday average. Set a weekend cap and redirect the difference.',
            'monthly_saving': round(float((weekend_avg - weekday_avg) * 4 / 30), 2),
            'priority_score': float(weekend_avg - weekday_avg),
            'icon': 'calendar',
        })

    # 7. Positive reinforcement
    monthly = _month_series(data)
    if len(monthly) >= 2 and monthly.iloc[-1] > monthly.iloc[-2]:
        delta = monthly.iloc[-1] - monthly.iloc[-2]
        recommendations.append({
            'type': 'savings',
            'title': 'Redirect your improving cash flow',
            'description': f'Net cash flow improved by ₹{delta:,.0f} versus last month. Move a part of this surplus to SIPs or emergency savings.',
            'monthly_saving': round(float(max(delta * 0.35, 0)), 2),
            'priority_score': float(max(delta, 0)),
            'icon': 'target',
        })

    archetype_bonus = {
        'subscription_heavy': 'subscription',
        'food_delivery_addict': 'habit',
        'impulse_shopper': 'spending_cut',
        'balanced_spender': 'savings',
        'saver': 'savings',
    }
    preferred = archetype_bonus.get(archetype)
    for rec in recommendations:
        rec['priority_score'] += 1200 if rec['type'] == preferred else 0

    final = []
    for idx, rec in enumerate(sorted(recommendations, key=lambda item: item['priority_score'], reverse=True)[:6], start=1):
        final.append({
            'id': f'rec_{idx:03d}',
            'type': rec['type'],
            'title': rec['title'],
            'description': rec['description'],
            'monthly_saving': round(float(rec['monthly_saving']), 2),
            'priority': idx,
            'icon': rec['icon'],
            'archetype': archetype,
        })
    return final
