import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_risky_csv(output_path):
    # Persona: Earning 70k, Spending 85k (Burning 15k/month)
    # Total starting balance: 1,00,000 -> Should cash out in ~6-7 months
    
    start_date = datetime(2023, 10, 1)
    end_date = datetime(2024, 4, 20)
    date_range = pd.date_range(start_date, end_date)
    
    data = []
    
    # Starting Balances
    balances = {
        'HDFC': 60000,
        'ICICI': 25000,
        'AXIS': 15000
    }
    
    # Monthly Salary (HDFC)
    for date in pd.date_range(start_date, end_date, freq='MS'):
        data.append([date.strftime('%Y-%m-%d'), 'HDFC', 'SALARY CREDIT', 70000, 0, 'Income', 'Income'])
        balances['HDFC'] += 70000
        
    # Recurring Expenses
    for date in pd.date_range(start_date, end_date, freq='MS'):
        # Rent (HDFC)
        data.append([(date + timedelta(days=4)).strftime('%Y-%m-%d'), 'HDFC', 'HOUSE RENT', -25000, 0, 'Rent', 'Expense'])
        balances['HDFC'] -= 25000
        # Car EMI (AXIS)
        data.append([(date + timedelta(days=9)).strftime('%Y-%m-%d'), 'AXIS', 'CAR LOAN EMI', -12000, 0, 'EMI', 'Expense'])
        balances['AXIS'] -= 12000
        # Insurance (ICICI)
        data.append([(date + timedelta(days=14)).strftime('%Y-%m-%d'), 'ICICI', 'HDFC LIFE PREMIUM', -8000, 0, 'Health', 'Expense'])
        balances['ICICI'] -= 8000
        # Internet/Phone (SBI -> AXIS)
        data.append([(date + timedelta(days=19)).strftime('%Y-%m-%d'), 'AXIS', 'AIRTEL BILL', -1500, 0, 'Utilities', 'Expense'])
        balances['AXIS'] -= 1500

    # Daily Variable Expenses (High Frequency)
    rng = np.random.default_rng(42)
    for current_date in date_range:
        # Food (HDFC) - approx 800/day
        if rng.random() < 0.8:
            amt = rng.integers(300, 1500)
            data.append([current_date.strftime('%Y-%m-%d'), 'HDFC', rng.choice(['Swiggy', 'Zomato', 'Blinkit']), -amt, 0, 'Food', 'Expense'])
            balances['HDFC'] -= amt
            
        # Shopping (ICICI) - approx 15k/month spread out
        if rng.random() < 0.2:
            amt = rng.integers(1500, 6000)
            data.append([current_date.strftime('%Y-%m-%d'), 'ICICI', rng.choice(['Amazon', 'Flipkart', 'Myntra']), -amt, 0, 'Shopping', 'Expense'])
            balances['ICICI'] -= amt

        # Transport (AXIS)
        if rng.random() < 0.3:
            amt = rng.integers(200, 800)
            data.append([current_date.strftime('%Y-%m-%d'), 'AXIS', rng.choice(['Uber', 'Ola', 'Petrol']), -amt, 0, 'Transport', 'Expense'])
            balances['AXIS'] -= amt

    # Convert to DataFrame to handle running balances correctly per bank
    df = pd.DataFrame(data, columns=['date', 'bank', 'description', 'amount', 'bank_balance', 'category', 'type'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['date'])
    
    # Recalculate bank_balance starting from initial values
    bank_current_balances = {
        'HDFC': 60000,
        'ICICI': 25000,
        'AXIS': 15000
    }
    
    for i in range(len(df)):
        bank = df.iloc[i]['bank']
        bank_current_balances[bank] += df.iloc[i]['amount']
        df.at[i, 'bank_balance'] = bank_current_balances[bank]
        
    df.to_csv(output_path, index=False)
    print(f"Risky dataset generated at {output_path}")

if __name__ == "__main__":
    import os
    target = 'c:/Users/user/Desktop/cashforecast-insurance-protection-module/cashforecast/data/risky_sample_dataset.csv'
    os.makedirs(os.path.dirname(target), exist_ok=True)
    generate_risky_csv(target)
