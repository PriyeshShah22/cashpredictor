from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


POLICY_KEYWORDS = {
    'life': ['lic', 'hdfc life', 'sbi life', 'icici prudential', 'max life', 'term insurance'],
    'health': ['star health', 'niva bupa', 'care health', 'religare', 'health insurance', 'mediclaim'],
    'vehicle': ['bajaj allianz', 'icici lombard', 'digit insurance', 'vehicle insurance', 'car insurance', 'bike insurance'],
    'travel': ['tata aig travel', 'icici travel', 'travel insurance'],
    'home': ['home protect', 'property insurance', 'home insurance'],
}

TRAVEL_KEYWORDS = [
    'makemytrip', 'air india', 'indigo', 'vistara', 'spicejet', 'goibibo', 'booking.com',
    'oyo', 'hotel', 'flight', 'travel', 'irctc', 'rail', 'train', 'trip',
]
FUEL_KEYWORDS = ['fuel', 'petrol', 'diesel', 'indian oil', 'bharat petroleum', 'hpcl', 'fastag']
HOMEOWNER_KEYWORDS = ['property tax', 'society maintenance', 'home loan', 'mortgage']

POLICY_LABELS = {
    'life': 'Term Life',
    'health': 'Health',
    'vehicle': 'Vehicle',
    'home': 'Home',
    'travel': 'Travel',
}


@dataclass
class PolicyDetection:
    covered: bool
    avg_premium: float = 0.0
    provider: str | None = None
    occurrences: int = 0
    last_seen: str | None = None


def _contains_keyword(value: str, keywords: Iterable[str]) -> bool:
    text = str(value or '').lower()
    return any(keyword in text for keyword in keywords)


def _safe_round(value: float) -> float:
    return round(float(value or 0), 2)


def _expense_frame(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data.copy()
    expense_mask = data['amount'] < 0
    transfer_mask = data.get('type', pd.Series('', index=data.index)).astype(str).str.lower().eq('transfer')
    return data[expense_mask & ~transfer_mask].copy()


def _income_frame(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data.copy()
    income_mask = data['amount'] > 0
    type_series = data.get('type', pd.Series('', index=data.index)).astype(str)
    category_series = data.get('category', pd.Series('', index=data.index)).astype(str)
    income_labeled = type_series.str.lower().eq('income') | category_series.str.lower().eq('income')
    return data[income_mask & income_labeled].copy()


def _monthly_income_estimate(data: pd.DataFrame) -> float:
    income = _income_frame(data)
    if income.empty:
        return 0.0
    monthly_income = income.groupby(income['date'].dt.to_period('M'))['amount'].sum()
    if monthly_income.empty:
        return 0.0
    return _safe_round(monthly_income.tail(6).mean())


def _spend_from_keywords(data: pd.DataFrame, keywords: Iterable[str]) -> float:
    expenses = _expense_frame(data)
    if expenses.empty:
        return 0.0
    mask = expenses['description'].astype(str).str.lower().apply(lambda value: _contains_keyword(value, keywords))
    return _safe_round(expenses.loc[mask, 'amount'].abs().sum())


def _category_spend(data: pd.DataFrame, category_name: str) -> float:
    expenses = _expense_frame(data)
    if expenses.empty:
        return 0.0
    mask = expenses.get('category', pd.Series('', index=expenses.index)).astype(str).str.lower().eq(category_name.lower())
    return _safe_round(expenses.loc[mask, 'amount'].abs().sum())


def _detect_policy(data: pd.DataFrame, policy_key: str) -> PolicyDetection:
    expenses = _expense_frame(data)
    if expenses.empty:
        return PolicyDetection(covered=False)

    keywords = POLICY_KEYWORDS[policy_key]
    mask = expenses['description'].astype(str).str.lower().apply(lambda value: _contains_keyword(value, keywords))
    matches = expenses.loc[mask].copy()
    if matches.empty:
        return PolicyDetection(covered=False)

    matches = matches.sort_values('date')
    latest_description = str(matches.iloc[-1]['description'])
    provider = next((keyword.title() for keyword in keywords if keyword in latest_description.lower()), latest_description)
    return PolicyDetection(
        covered=True,
        avg_premium=_safe_round(matches['amount'].abs().mean()),
        provider=provider,
        occurrences=int(len(matches)),
        last_seen=matches.iloc[-1]['date'].strftime('%Y-%m-%d'),
    )


def _family_size_proxy(monthly_income: float, expenses: pd.DataFrame, medical_spend: float) -> int:
    monthly_spend = 0.0
    if not expenses.empty:
        monthly_totals = expenses.groupby(expenses['date'].dt.to_period('M'))['amount'].sum().abs()
        monthly_spend = float(monthly_totals.tail(6).mean()) if not monthly_totals.empty else 0.0

    score = 1
    if monthly_income >= 120000 or monthly_spend >= 70000:
        score += 2
    elif monthly_income >= 60000 or monthly_spend >= 35000:
        score += 1
    if medical_spend >= 12000:
        score += 1
    return max(1, min(score, 5))


def _risk_to_points(level: str) -> int:
    return {'LOW': 10, 'MEDIUM': 20, 'HIGH': 30}.get(level, 0)


def analyze_insurance_protection(data: pd.DataFrame) -> dict:
    if data is None or data.empty:
        return {
            'insurance_summary': {key: {
                'label': POLICY_LABELS[key],
                'covered': False,
                'status': 'NO_DATA',
                'gap_level': 'LOW',
                'average_premium': 0.0,
                'recommended_cover_amount': 0.0,
                'explanation': 'Upload bank statements to unlock insurance intelligence.',
                'suggested_action': 'Upload more transaction history',
            } for key in POLICY_LABELS},
            'overall_risk_score': 0,
            'missing_policies': [],
            'recommendations': [],
            'message': 'No transaction data available for insurance analysis.',
        }

    working = data.copy()
    working['date'] = pd.to_datetime(working['date'])
    expenses = _expense_frame(working)

    monthly_income = _monthly_income_estimate(working)
    annual_income = _safe_round(monthly_income * 12)
    medical_spend = _category_spend(working, 'Health')
    rent_spend = _category_spend(working, 'Rent')
    fuel_spend = _spend_from_keywords(working, FUEL_KEYWORDS)
    travel_spend = _spend_from_keywords(working, TRAVEL_KEYWORDS)
    travel_txn_count = int(_expense_frame(working)['description'].astype(str).str.lower().apply(lambda value: _contains_keyword(value, TRAVEL_KEYWORDS)).sum()) if not expenses.empty else 0
    homeowner_signal = rent_spend == 0 and (monthly_income >= 50000 or _spend_from_keywords(working, HOMEOWNER_KEYWORDS) > 0)
    family_size = _family_size_proxy(monthly_income, expenses, medical_spend)

    life_detection = _detect_policy(working, 'life')
    health_detection = _detect_policy(working, 'health')
    vehicle_detection = _detect_policy(working, 'vehicle')
    home_detection = _detect_policy(working, 'home')
    travel_detection = _detect_policy(working, 'travel')

    health_cover = family_size * 300000
    life_cover = annual_income * 15 if annual_income > 0 else 0

    insurance_summary = {}
    recommendations = []
    missing_policies = []
    total_points = 0

    def add_policy(policy_key: str, covered: bool, gap_level: str, recommended_cover: float, explanation: str, suggested_action: str, detection: PolicyDetection):
        nonlocal total_points
        total_points += _risk_to_points(gap_level)
        status = 'COVERED' if covered else ('NEEDS_ATTENTION' if gap_level == 'MEDIUM' else 'MISSING')
        if not covered and gap_level in {'HIGH', 'MEDIUM'}:
            missing_policies.append(policy_key)
            recommendations.append({
                'policy': policy_key,
                'label': POLICY_LABELS[policy_key],
                'gap_level': gap_level,
                'recommended_cover_amount': _safe_round(recommended_cover),
                'suggested_action': suggested_action,
                'explanation': explanation,
            })
        insurance_summary[policy_key] = {
            'label': POLICY_LABELS[policy_key],
            'covered': covered,
            'status': status,
            'gap_level': gap_level,
            'average_premium': _safe_round(detection.avg_premium),
            'detected_provider': detection.provider,
            'occurrences': detection.occurrences,
            'last_seen': detection.last_seen,
            'recommended_cover_amount': _safe_round(recommended_cover),
            'explanation': explanation,
            'suggested_action': suggested_action,
        }

    life_gap = 'LOW' if life_detection.covered else ('HIGH' if life_cover > 0 else 'MEDIUM')
    life_explanation = (
        f"Existing life insurance premium detected around ₹{life_detection.avg_premium:,.0f}."
        if life_detection.covered
        else f"No life insurance detected. Based on an estimated annual income of ₹{annual_income:,.0f}, recommended term cover is about ₹{life_cover:,.0f}."
    )
    add_policy('life', life_detection.covered, life_gap, life_cover, life_explanation, 'Secure or review term life cover to protect dependents.', life_detection)

    high_medical_pressure = medical_spend >= max(8000, monthly_income * 0.08 if monthly_income else 8000)
    health_gap = 'LOW' if health_detection.covered else ('HIGH' if high_medical_pressure else 'MEDIUM')
    health_explanation = (
        f"Health insurance premium detected around ₹{health_detection.avg_premium:,.0f}."
        if health_detection.covered
        else f"Medical spending is ₹{medical_spend:,.0f}. With a family-size proxy of {family_size}, suggested health cover is about ₹{health_cover:,.0f}."
    )
    add_policy('health', health_detection.covered, health_gap, health_cover, health_explanation, 'Add a health policy or top-up cover to reduce hospitalization risk.', health_detection)

    has_vehicle_signal = fuel_spend > 0
    vehicle_gap = 'LOW' if vehicle_detection.covered else ('HIGH' if has_vehicle_signal else 'LOW')
    vehicle_explanation = (
        f"Vehicle insurance premium detected around ₹{vehicle_detection.avg_premium:,.0f}."
        if vehicle_detection.covered
        else (f"Fuel and mobility transactions total ₹{fuel_spend:,.0f}, which suggests active vehicle usage without matching vehicle insurance." if has_vehicle_signal else 'No clear vehicle-use signal detected from transactions.')
    )
    add_policy('vehicle', vehicle_detection.covered, vehicle_gap, max(fuel_spend * 20, 0), vehicle_explanation, 'Review motor insurance cover if you actively use a car or bike.', vehicle_detection)

    home_gap = 'LOW' if home_detection.covered else ('MEDIUM' if homeowner_signal else 'LOW')
    home_explanation = (
        f"Home/property insurance premium detected around ₹{home_detection.avg_premium:,.0f}."
        if home_detection.covered
        else ('No rent payments detected and income is stable, so a homeowner profile is possible. Home protection is worth reviewing.' if homeowner_signal else 'Rent transactions are present, so home insurance is not a strong gap signal right now.')
    )
    add_policy('home', home_detection.covered, home_gap, max(monthly_income * 24, 0), home_explanation, 'Consider home structure or contents insurance if you own the property.', home_detection)

    frequent_travel = travel_txn_count >= 3 or travel_spend >= max(5000, monthly_income * 0.05 if monthly_income else 5000)
    travel_gap = 'LOW' if travel_detection.covered else ('MEDIUM' if frequent_travel else 'LOW')
    travel_explanation = (
        f"Travel insurance premium detected around ₹{travel_detection.avg_premium:,.0f}."
        if travel_detection.covered
        else (f"Travel-linked transactions appear {travel_txn_count} times with spend of ₹{travel_spend:,.0f}, suggesting optional travel cover could help on upcoming trips." if frequent_travel else 'No strong recurring travel pattern detected yet.')
    )
    add_policy('travel', travel_detection.covered, travel_gap, max(travel_spend * 4, 0), travel_explanation, 'Add trip cover when travel activity becomes frequent or higher value.', travel_detection)

    overall_risk_score = max(0, min(100, int(round(total_points / 150 * 100))))

    return {
        'insurance_summary': insurance_summary,
        'overall_risk_score': overall_risk_score,
        'missing_policies': missing_policies,
        'recommendations': recommendations,
        'user_profile': {
            'estimated_monthly_income': _safe_round(monthly_income),
            'estimated_annual_income': _safe_round(annual_income),
            'family_size_proxy': family_size,
            'category_spends': {
                'medical': _safe_round(medical_spend),
                'travel': _safe_round(travel_spend),
                'fuel': _safe_round(fuel_spend),
                'rent': _safe_round(rent_spend),
            },
        },
    }
