from __future__ import annotations

from pathlib import Path

from models.anomaly_detector import detect_anomalies
from models.cashout_predictor import predict_cashout
from models.category_classifier import classify_description
from models.health_scorer import calculate_health_score
from models.recommendation_engine import generate_recommendations
from scripts.generate_dataset import ensure_demo_dataset
from scripts.normalize_data import normalize_file


def validate_pipeline(csv_path: str):
    print('1. Loading and normalizing...')
    ensure_demo_dataset(Path(__file__).resolve().parents[1])
    df = normalize_file(csv_path)
    assert len(df) > 0, 'ERROR: Normalization produced empty dataframe'
    assert all(col in df.columns for col in ['date', 'bank', 'description', 'amount', 'bank_balance']), 'ERROR: Missing required columns'

    print('2. Classifying categories...')
    df['category'] = df['description'].apply(classify_description)
    assert df['category'].notna().all(), 'ERROR: Null categories found'

    print('3. Running cashout prediction...')
    forecast, lower, upper, cashout_days = predict_cashout(df)
    assert cashout_days > 0, 'ERROR: Cashout prediction failed'

    print('4. Detecting anomalies...')
    anomalies = detect_anomalies(df)
    assert isinstance(anomalies, list), 'ERROR: Anomaly detector returned wrong type'

    print('5. Generating recommendations...')
    recs = generate_recommendations(df, {}, {'total_income': 1, 'total_spending': abs(df[df['amount'] < 0]['amount'].sum()), 'current_balance': float(df['bank_balance'].iloc[-1])})
    assert isinstance(recs, list), 'ERROR: Recommendation engine failed'

    print('6. Scoring health...')
    score = calculate_health_score(df, {'total_income': max(float(df[df['amount'] > 0]['amount'].sum()), 1), 'total_spending': abs(float(df[df['amount'] < 0]['amount'].sum()))}, anomalies)
    assert 0 <= score['overall'] <= 100, 'ERROR: Health score out of range'

    print(f"\n✅ Pipeline validation PASSED — {len(df)} transactions, {cashout_days} days to cashout")
    return True


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    ensure_demo_dataset(root)
    validate_pipeline(str(root / 'data' / 'raw' / 'hdfc_statement.csv'))
