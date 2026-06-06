from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

try:
    from statsmodels.tsa.arima.model import ARIMA
except Exception:  # pragma: no cover - optional dependency fallback
    ARIMA = None


MODEL_NAME = 'LinearRegression+ARIMA'


def _build_daily_balance(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    data = data.sort_values('date')
    daily = data.groupby('date').agg(
        bank_balance=('bank_balance', 'last'),
        spend=('amount', lambda s: abs(s[s < 0].sum())),
        income=('amount', lambda s: s[s > 0].sum()),
    ).reset_index()
    full_range = pd.date_range(daily['date'].min(), daily['date'].max(), freq='D')
    daily = daily.set_index('date').reindex(full_range)
    daily.index.name = 'date'
    daily['bank_balance'] = daily['bank_balance'].ffill().bfill()
    daily['spend'] = daily['spend'].fillna(0)
    daily['income'] = daily['income'].fillna(0)
    daily = daily.reset_index()
    daily['day_index'] = np.arange(len(daily))
    daily['avg_7d_spend'] = daily['spend'].rolling(7, min_periods=1).mean()
    daily['avg_7d_income'] = daily['income'].rolling(7, min_periods=1).mean()
    daily['day_of_week'] = daily['date'].dt.dayofweek
    return daily


def predict_cashout(df: pd.DataFrame, days_ahead: int = 60):
    daily = _build_daily_balance(df)
    y = daily['bank_balance'].astype(float).values
    X = daily[['day_index', 'avg_7d_spend', 'avg_7d_income', 'day_of_week']].values
    lr = LinearRegression().fit(X, y)

    future_dates = pd.date_range(daily['date'].iloc[-1] + timedelta(days=1), periods=days_ahead, freq='D')
    future = pd.DataFrame({'date': future_dates})
    future['day_index'] = np.arange(len(daily), len(daily) + days_ahead)
    future['avg_7d_spend'] = daily['avg_7d_spend'].tail(7).mean()
    future['avg_7d_income'] = daily['avg_7d_income'].tail(7).mean()
    future['day_of_week'] = future['date'].dt.dayofweek
    future_X = future[['day_index', 'avg_7d_spend', 'avg_7d_income', 'day_of_week']].values
    lr_pred = lr.predict(future_X).flatten()

    try:
        if ARIMA is None:
            raise ImportError('statsmodels is not available')
        arima_model = ARIMA(y, order=(2, 1, 2)).fit()
        arima_pred = np.asarray(arima_model.forecast(steps=days_ahead)).flatten()
        fitted = np.asarray(arima_model.predict(start=0, end=len(y) - 1, typ='levels')).flatten()
    except Exception:
        arima_pred = lr_pred.copy()
        fitted = lr.predict(X).flatten()

    ensemble = 0.4 * lr_pred + 0.6 * arima_pred
    baseline_fit = 0.4 * lr.predict(X).flatten() + 0.6 * fitted[: len(y)]
    residuals = y - baseline_fit
    std = float(np.std(residuals)) if len(residuals) > 1 else 0.0
    lower = ensemble - 1.96 * std
    upper = ensemble + 1.96 * std
    cashout_days = next((i + 1 for i, value in enumerate(ensemble) if value <= 0), None)
    
    if cashout_days is None:
        # Extrapolate based on historical net daily flow if we don't hit 0 in the forecast window
        net_daily = daily['income'].mean() - daily['spend'].mean()
        if net_daily < -0.1: # Burning cash
            cashout_days = int(y[-1] / abs(net_daily))
        else:
            cashout_days = 999999 # Technically growing, but we give it a massive runway instead of 999
            
    if y[-1] < 0:
        cashout_days = 0 # Already negative
        
    cashout_days = max(0, cashout_days)
    
    return ensemble, lower, upper, cashout_days


def forecast_balance(df: pd.DataFrame, days_ahead: int = 60) -> dict:
    daily = _build_daily_balance(df)
    ensemble, lower, upper, cashout_days = predict_cashout(df, days_ahead=days_ahead)
    future_dates = pd.date_range(daily['date'].iloc[-1] + timedelta(days=1), periods=days_ahead, freq='D')
    hist = daily.tail(90)
    confidence = float(max(0.5, min(0.95, 1 - (np.std(np.diff(hist['bank_balance'])) / (hist['bank_balance'].abs().mean() + 1)))))
    predicted = []
    for idx, date in enumerate(future_dates):
        predicted.append({
            'date': date.strftime('%Y-%m-%d'),
            'balance': round(float(ensemble[idx]), 2),
            'lower': round(float(lower[idx]), 2),
            'upper': round(float(upper[idx]), 2),
        })
    historical = [
        {'date': row.date.strftime('%Y-%m-%d'), 'balance': round(float(row.bank_balance), 2)}
        for row in hist.itertuples(index=False)
    ]
    # Cap the days for date calculation to prevent OverflowError (max year 9999)
    safe_days = min(int(cashout_days), 36500) 
    cashout_date = (daily['date'].iloc[-1] + timedelta(days=safe_days)).strftime('%d %b %Y')
    if int(cashout_days) >= 36500:
        cashout_date = "Safe (100+ years)"
    return {
        'historical': historical,
        'predicted': predicted,
        'model_used': MODEL_NAME,
        'confidence': round(confidence, 2),
        'cashout_days': int(cashout_days),
        'cashout_date': cashout_date,
    }
