from __future__ import annotations

import math

import pandas as pd


def infer_risk_score(summary: dict, spending_by_category: dict, df: pd.DataFrame) -> float:
    income = float(summary.get('total_income', 0) or 0)
    spend = float(summary.get('total_spending', 0) or 0)
    surplus_ratio = max(0.0, (income - spend) / income) if income else 0.0
    volatility = float(df[df['amount'] < 0]['amount'].abs().std() / (df[df['amount'] < 0]['amount'].abs().mean() + 1)) if len(df[df['amount'] < 0]) > 3 else 0.5
    shopping_share = float(spending_by_category.get('Shopping', 0) / max(spend, 1)) if spend else 0.0
    food_share = float(spending_by_category.get('Food', 0) / max(spend, 1)) if spend else 0.0
    score = 0.55 * surplus_ratio + 0.2 * (1 - min(volatility, 1)) + 0.15 * (1 - shopping_share) + 0.10 * (1 - food_share)
    return round(max(0.05, min(0.95, score)), 2)


def calculate_allocation(monthly_surplus: float, risk_score: float) -> dict:
    if risk_score < 0.3:
        split = {
            'Emergency Fund': 0.35,
            'Fixed Deposit': 0.30,
            'Debt Mutual Fund': 0.20,
            'Equity Mutual Fund': 0.10,
            'Digital Gold': 0.05,
        }
    elif risk_score < 0.6:
        split = {
            'Emergency Fund': 0.25,
            'Fixed Deposit': 0.20,
            'Debt Mutual Fund': 0.15,
            'Equity Mutual Fund': 0.30,
            'Digital Gold': 0.10,
        }
    else:
        split = {
            'Emergency Fund': 0.15,
            'Fixed Deposit': 0.10,
            'Debt Mutual Fund': 0.10,
            'Equity Mutual Fund': 0.55,
            'Digital Gold': 0.10,
        }
    return {
        key: {'percent': round(value * 100), 'amount': round(monthly_surplus * value, 2)}
        for key, value in split.items()
    }


def calculate_sip_projection(monthly_sip: float, years: int = 10, rate: float = 0.12) -> float:
    monthly_rate = rate / 12
    months = years * 12
    if monthly_rate == 0:
        return round(monthly_sip * months, 2)
    fv = monthly_sip * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate)
    return round(float(fv), 2)


def build_investment_plan(summary: dict, spending_by_category: dict, df: pd.DataFrame) -> dict:
    monthly_surplus = float(summary.get('monthly_surplus', 0) or 0)
    investable = max(0.0, monthly_surplus)
    risk_score = infer_risk_score(summary, spending_by_category, df)
    allocation = calculate_allocation(investable, risk_score)
    sip_recommendation = round(investable * (0.25 if risk_score < 0.3 else 0.35 if risk_score < 0.6 else 0.45), 2)
    sip_projection = [
        {'year': 1, 'value': calculate_sip_projection(sip_recommendation, 1, 0.12)},
        {'year': 3, 'value': calculate_sip_projection(sip_recommendation, 3, 0.12)},
        {'year': 5, 'value': calculate_sip_projection(sip_recommendation, 5, 0.12)},
        {'year': 10, 'value': calculate_sip_projection(sip_recommendation, 10, 0.12)},
    ]
    keep_liquid = round(investable * 0.2, 2)
    return {
        'monthly_investable': round(investable, 2),
        'risk_score': risk_score,
        'allocation': allocation,
        'sip_recommendation': sip_recommendation,
        'sip_projection': sip_projection,
        'save_vs_invest': {
            'save': round(investable * 0.35, 2),
            'invest': round(investable * 0.45, 2),
            'keep_liquid': keep_liquid,
        },
    }
