from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

KEYWORD_MAP = {
    'Food': ['blinkit', 'swiggy', 'zomato', 'dominos', 'subway', 'mcdonalds', 'reliance fresh', 'bigbasket', 'grocer', 'dmart', 'restaurant', 'starbucks', 'instamart'],
    'Transport': ['ola', 'uber', 'fastag', 'petrol', 'fuel', 'irctc', 'makemytrip', 'metro', 'rapido'],
    'Subscriptions': ['netflix', 'spotify', 'amazon prime', 'hotstar', 'youtube', 'google one', 'apple', 'prime video'],
    'Utilities': ['png gas', 'electricity', 'bescom', 'tata power', 'jio', 'airtel', 'internet', 'broadband', 'water bill', 'wifi'],
    'Shopping': ['amazon', 'flipkart', 'myntra', 'ajio', 'nykaa', 'meesho', 'ikea'],
    'Health': ['pharmacy', 'apollo', 'medplus', 'hospital', 'clinic', 'health'],
    'Entertainment': ['bookmyshow', 'steam', 'playstation', 'inox', 'pvr', 'gaming'],
    'Education': ['udemy', 'coursera', 'books', 'tuition', 'course'],
    'Income': ['salary', 'credit - acme', 'freelance', 'income', 'refund', 'bonus'],
    'Rent': ['rent', 'landlord', 'housing'],
    'EMI': ['emi', 'loan', 'hdfc bank emi', 'bajaj finance'],
    'Investment': ['mutual fund', 'sip', 'zerodha', 'groww', 'stock', 'mf', 'nps'],
    'Transfer': ['imps to', 'upi to', 'neft to', 'transfer', 'upi/p2p', 'wallet transfer'],
}

CATEGORY_TO_TYPE = {
    'Income': 'Income',
    'Transfer': 'Transfer',
    'Investment': 'Investment',
    'Rent': 'Expense',
    'EMI': 'Expense',
    'Food': 'Expense',
    'Transport': 'Expense',
    'Subscriptions': 'Expense',
    'Utilities': 'Expense',
    'Shopping': 'Expense',
    'Health': 'Expense',
    'Entertainment': 'Expense',
    'Education': 'Expense',
    'Others': 'Expense',
}


@dataclass
class CategoryModel:
    pipeline: Optional[Pipeline] = None

    def predict(self, descriptions: pd.Series) -> pd.Series:
        base = descriptions.fillna('').astype(str).apply(classify_description)
        if self.pipeline is None:
            return base
        prediction = pd.Series(self.pipeline.predict(descriptions.fillna('').astype(str)), index=descriptions.index)
        prediction = prediction.where(prediction.notna(), base)
        prediction = prediction.mask(prediction.eq('Others'), base)
        return prediction


def classify_description(description: str) -> str:
    desc_lower = str(description or '').lower()
    for category, keywords in KEYWORD_MAP.items():
        if any(keyword in desc_lower for keyword in keywords):
            return category
    return 'Others'


def broad_type_from_category(category: str) -> str:
    return CATEGORY_TO_TYPE.get(category, 'Expense')


def build_ml_classifier(df: pd.DataFrame) -> CategoryModel:
    df = df.copy()
    df['description'] = df['description'].fillna('').astype(str)
    df['seed_category'] = df['description'].apply(classify_description)
    labeled = df[df['seed_category'] != 'Others']

    if len(labeled) < 20 or labeled['seed_category'].nunique() < 2:
        return CategoryModel(None)

    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), max_features=1500)),
        ('clf', LogisticRegression(max_iter=600, random_state=42)),
    ])
    pipeline.fit(labeled['description'], labeled['seed_category'])
    return CategoryModel(pipeline)


def assign_categories(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        df['category'] = []
        df['type'] = []
        return df
    model = build_ml_classifier(df)
    result = df.copy()
    result['category'] = model.predict(result['description'])
    result['type'] = result['category'].apply(broad_type_from_category)
    income_mask = result['amount'] > 0
    transfer_desc = result['description'].str.lower().str.contains('transfer|upi to|neft|imps', na=False)
    result.loc[income_mask & result['category'].eq('Others'), 'category'] = 'Income'
    result.loc[income_mask & result['type'].ne('Transfer'), 'type'] = 'Income'
    result.loc[transfer_desc, 'type'] = 'Transfer'
    result.loc[transfer_desc & result['category'].eq('Others'), 'category'] = 'Transfer'
    return result
