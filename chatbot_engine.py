from __future__ import annotations
import re

class NexusChatbot:
    def __init__(self, analysis: dict):
        self.d = analysis

    def _fmt(self, v) -> str:
        return f"₹{abs(float(v)):,.2f}"

    def _match(self, q: str, kws: list) -> bool:
        return any(k in q for k in kws)

    def respond(self, query: str) -> dict:
        # Step 1: Pre-process for grammar correction and typos
        q_raw = query.strip()
        q = self._pre_process(q_raw.lower())

        # Step 2: NEW! Compare Engine (X vs Y)
        comp = self._compare_domains(q)
        if comp: return {'response': comp}

        # Step 3: Domain Summary (Group by merchant/category)
        domain = self._domain_summary(q)
        if domain: return {'response': domain}

        # Step 4: Transaction Navigation
        nav = self._transaction_navigation(q)
        if nav: return nav

        # Step 5: Loan Advice & NEW! Affordability Engine
        afford = self._affordability(q)
        if afford: return {'response': afford}
        
        loan = self._loan_advice(q)
        if loan: return {'response': loan}

        # Step 6: Rule-based handlers including NEW! Top Expense
        for fn in [
            self._top_expense, self._greeting, self._balance, self._cashout, self._burn,
            self._income, self._anomalies, self._health, self._category,
            self._leaks, self._recs, self._recurring, self._banks,
            self._dow, self._goals, self._invest, self._help,
        ]:
            r = fn(q)
            if r: return {'response': r}
            
        return {'response': f"I'm not sure about that. Try asking: 'Can I afford a laptop for 50000?', 'Swiggy vs Zomato', or 'What was my biggest purchase?'"}

    def _pre_process(self, q: str) -> str:
        # Common grammar/typo corrections for financial queries
        corrections = {
            'spent': ['spend', 'spending', 'spended', 'spnt'],
            'balance': ['balence', 'bal', 'balanc'],
            'transaction': ['transection', 'transac', 'txn', 'txns'],
            'salary': ['salery', 'income', 'earning'],
            'recurring': ['recuring', 'subscribtion', 'bill'],
            'cashout': ['cash out', 'money last', 'run out'],
            'swiggy': ['swigy', 'swiggy order'],
            'zomato': ['zomatoo', 'zomato order'],
            'amazon': ['amazn', 'amzon'],
            'netflix': ['netfliz', 'netflx', 'netflic', 'netfilx'],
        }
        words = q.split()
        corrected = []
        for word in words:
            found = False
            for canonical, typos in corrections.items():
                if word in typos or word == canonical:
                    corrected.append(canonical)
                    found = True
                    break
            if not found:
                corrected.append(word)
        return " ".join(corrected)

    def _domain_summary(self, q: str) -> str | None:
        # Define intents
        is_max = any(kw in q for kw in ['largest', 'max', 'biggest', 'highest', 'most'])
        is_min = any(kw in q for kw in ['smallest', 'min', 'lowest', 'least'])
        is_avg = any(kw in q for kw in ['average', 'avg'])
        is_sum = any(kw in q for kw in ['total', 'sum', 'summary', 'all'])
        is_spend = any(kw in q for kw in ['spent', 'spend', 'spending', 'pay', 'paid'])
        
        # If no analytical intent is detected, fall back to other handlers
        if not (is_max or is_min or is_avg or is_sum or is_spend):
            return None
            
        target = None
        # Extract target after prepositions (e.g., "... on Amazon", "... in groceries")
        match = re.search(r'\b(in|on|for|of|to|at)\s+(.+)', q)
        if match:
            target = match.group(2).strip()
        else:
            # Fallback: Strip intent words and see what's left
            words_to_remove = [
                'largest', 'max', 'biggest', 'highest', 'smallest', 'min', 'lowest', 
                'average', 'avg', 'total', 'sum', 'summary', 'all', 'amount', 'payment', 
                'spent', 'spend', 'spending', 'transaction', 'transactions', 'how', 
                'much', 'did', 'i', 'pay', 'paid', 'the', 'my', 'a', 'an', 'is', 'what', 'was'
            ]
            clean_q = " ".join([w for w in q.split() if w not in words_to_remove])
            if clean_q:
                target = clean_q
                
        if not target or len(target) < 2:
            return None
            
        # Clean punctuation
        target = re.sub(r'[^a-zA-Z0-9\s]', '', target).strip()
        
        txs = self.d.get('transactions', [])
        matches = [t for t in txs if target in t['description'].lower() or target in t['category'].lower()]
        
        if matches:
            amounts = [abs(float(t['amount'])) for t in matches if float(t['amount']) < 0]
            total_spent = sum(amounts)
            total_income = sum(float(t['amount']) for t in matches if float(t['amount']) > 0)
            count = len(matches)

            res = f"📝 **NLP Analysis for '{target.title()}'**\n"
            res += f"Found {count} transaction(s).\n"
            
            if amounts:
                if is_max:
                    res += f"🏆 **Largest Transaction: {self._fmt(max(amounts))}**\n"
                elif is_min:
                    res += f"📉 **Smallest Transaction: {self._fmt(min(amounts))}**\n"
                elif is_avg:
                    res += f"📊 **Average Spending: {self._fmt(total_spent / len(amounts))}**\n"
                
                res += f"💸 Total spent: {self._fmt(total_spent)}\n"
                if count > 1 and not (is_max or is_min or is_avg):
                    res += f"📈 Max: {self._fmt(max(amounts))} | Min: {self._fmt(min(amounts))}\n"
                    res += f"📊 Average: {self._fmt(total_spent / len(amounts))}\n"
            
            if total_income > 0:
                res += f"💰 Total received: {self._fmt(total_income)}\n"
            
            if count > 1:
                merchants = {}
                for t in matches:
                    merchants[t['description']] = merchants.get(t['description'], 0) + abs(float(t['amount']))
                top_m = max(merchants, key=merchants.get)
                res += f"🏆 Top merchant: {top_m} ({self._fmt(merchants[top_m])})"
            return res
        
        # If we successfully identified an intent and a target, but found no transactions,
        # return a clear message instead of falling back to navigation.
        return f"I couldn't find any transactions for '{target.title()}' to analyze."


    def _loan_advice(self, q):
        if not self._match(q, ['loan', 'borrow', 'credit card', 'mortgage', 'emi']):
            return None
        h = self.d.get('health_score', {})
        score = h.get('overall', 0)
        s = self.d.get('summary', {})
        surplus = s.get('monthly_surplus', 0)
        burn = s.get('daily_burn_rate', 0) * 30
        if score >= 75:
            return (f"🏦 **Loan Status: RECOMMENDED**\n"
                    f"Your health score is excellent ({score}/100). With a monthly surplus of {self._fmt(surplus)}, "
                    "you can comfortably handle an EMI up to 30% of your income.")
        elif score >= 50:
            return (f"⚖️ **Loan Status: PROCEED WITH CAUTION**\n"
                    f"Your health score is fair ({score}/100). Reduce your monthly burn ({self._fmt(burn)}) by 10% first to improve your debt-to-income ratio.")
        else:
            return (f"⚠️ **Loan Status: NOT RECOMMENDED**\n"
                    f"Your financial health score is low ({score}/100). Taking a loan now may put you in a debt trap. "
                    f"Focus on extending your {s.get('days_remaining')} day runway first.")

    def _affordability(self, q: str) -> str | None:
        if not self._match(q, ['can i afford', 'should i buy', 'can i buy']):
            return None
            
        import math
        match = re.search(r'(afford|buy)\s+(.+?)\s+(for|worth|of)\s+₹?(\d+[,\d]*)', q)
        if not match:
            match_num = re.search(r'₹?(\d+[,\d]*)', q)
            if match_num:
                price_str = match_num.group(1).replace(',', '')
                item = "that purchase"
                price = float(price_str)
            else:
                return "I can help you check if you can afford something! Try asking: 'Can I afford a laptop for 50000?'"
        else:
            item = match.group(2).strip()
            item = re.sub(r'^(a|an|the|new)\s+', '', item)
            price_str = match.group(4).replace(',', '')
            price = float(price_str)
            
        s = self.d.get('summary', {})
        balance = float(str(s.get('current_balance', 0)).replace(',', '').replace('₹', ''))
        surplus = float(str(s.get('monthly_surplus', 0)).replace(',', '').replace('₹', ''))
        
        if price > balance:
            months_needed = math.ceil((price - balance) / surplus) if surplus > 0 else 'infinity'
            if surplus > 0:
                return f"🚫 **Not right now.** You have {self._fmt(balance)}, which isn't enough for {item.title()} ({self._fmt(price)}).\nHowever, with your monthly surplus of {self._fmt(surplus)}, you can save up for it in about **{months_needed} months**!"
            else:
                return f"🚫 **No.** You don't have enough balance, and you are currently burning cash every month. Focus on reducing expenses first!"
                
        remaining = balance - price
        percent = (price / balance) * 100
        
        if percent > 50:
            return f"⚠️ **Proceed with Caution.** You *can* afford {item.title()} ({self._fmt(price)}), but it will wipe out **{percent:.1f}%** of your liquid balance! You'll be left with {self._fmt(remaining)}."
        elif percent > 20:
            return f"⚖️ **Think about it.** It costs {self._fmt(price)}, which is {percent:.1f}% of your balance. You'll still have {self._fmt(remaining)} left, but maybe wait a few days before deciding."
        else:
            return f"✅ **Yes, absolutely!** {item.title()} ({self._fmt(price)}) is only {percent:.1f}% of your current balance. It won't significantly impact your financial health."

    def _compare_domains(self, q: str) -> str | None:
        if not self._match(q, ['vs', 'compare', 'versus']):
            return None
            
        match = re.search(r'(compare\s+)?(.+?)\s+(vs|versus|and)\s+(.+)', q)
        if not match:
            return None
            
        target1 = match.group(2).strip()
        target2 = match.group(4).strip()
        
        for w in ['compare', 'spending', 'on', 'in', 'between']:
            target1 = target1.replace(w, '').strip()
        target2 = re.sub(r'[^a-zA-Z0-9\s]', '', target2).strip()
        target1 = re.sub(r'[^a-zA-Z0-9\s]', '', target1).strip()
        
        if not target1 or not target2:
            return None
            
        txs = self.d.get('transactions', [])
        amt1 = sum(abs(float(t['amount'])) for t in txs if float(t['amount']) < 0 and (target1.lower() in t['description'].lower() or target1.lower() in t['category'].lower()))
        amt2 = sum(abs(float(t['amount'])) for t in txs if float(t['amount']) < 0 and (target2.lower() in t['description'].lower() or target2.lower() in t['category'].lower()))
        
        if amt1 == 0 and amt2 == 0:
            return f"I couldn't find any spending for either '{target1.title()}' or '{target2.title()}' to compare."
            
        res = f"🥊 **Spending Showdown: {target1.title()} vs {target2.title()}**\n\n"
        res += f"🔹 **{target1.title()}**: {self._fmt(amt1)}\n"
        res += f"🔹 **{target2.title()}**: {self._fmt(amt2)}\n\n"
        
        if amt1 > amt2:
            res += f"🏆 You spend significantly more on **{target1.title()}** (+{self._fmt(amt1 - amt2)})."
        elif amt2 > amt1:
            res += f"🏆 You spend significantly more on **{target2.title()}** (+{self._fmt(amt2 - amt1)})."
        else:
            res += "Wow, it's an exact tie!"
            
        return res

    def _top_expense(self, q: str) -> str | None:
        if not self._match(q, ['biggest expense overall', 'largest transaction overall', 'my biggest purchase', 'largest expense', 'biggest purchase']):
            return None
            
        txs = self.d.get('transactions', [])
        expenses = [t for t in txs if float(t['amount']) < 0]
        if not expenses:
            return "No expenses found in your history."
            
        top_txn = max(expenses, key=lambda x: abs(float(x['amount'])))
        return f"🚨 **Your Biggest Single Purchase**\n\nOn {top_txn['date']}, you spent **{self._fmt(top_txn['amount'])}** at **{top_txn['description']}** ({top_txn['category']})."

    def _transaction_navigation(self, q):
        if not self._match(q, ['show', 'find', 'transaction', 'spent', 'pay', 'bought']):
            return None
        search_term = q
        fillers = [
            'show me my payment to', 'show me my transaction for', 'show me my',
            'find my transaction for', 'find my payment to', 'find my',
            'transaction for', 'spent on', 'payment to', 'show me', 'find', 'show'
        ]
        for f in fillers:
            if search_term.startswith(f):
                search_term = search_term.replace(f, '', 1).strip()
                break
        search_term = re.sub(r'^(for|the|my|a|an)\s+', '', search_term).strip()
        if not search_term or len(search_term) < 2:
            if 'transaction' in q:
                return {'response': "Sure! Navigating to your Transactions tab.", 'command': 'NAVIGATE:TRANSACTIONS'}
            return None
        txs = self.d.get('transactions', [])
        found = [t for t in txs if search_term in t['description'].lower()]
        if found:
            t = found[0]
            return {
                'response': f"🔍 Found it! You spent {self._fmt(t['amount'])} at **{t['description']}** on {t['date']}. Navigating now...",
                'command': f"GOTO_TRANSACTION:{t['description']}",
            }
        return {'response': f"No transactions found matching '{search_term}'. Try a shorter keyword?"}

    def _greeting(self, q):
        if self._match(q, ['hi', 'hello', 'hey']):
            s = self.d.get('summary', {})
            banks = self.d.get('connected_banks', [])
            return (f"Hi! I'm ForeCashy AI 🤖\nYou have {len(banks)} bank(s): {', '.join(banks) or 'none'}.\n"
                    f"Balance: {self._fmt(s.get('current_balance', 0))}.\n"
                    "Ask me about spending, cashout forecast, loans, or find specific transactions!")
        return None

    def _balance(self, q):
        if self._match(q, ['balance', 'how much money', 'how much do i have', 'funds']):
            s = self.d.get('summary', {})
            bb = self.d.get('bank_balances', {})
            lines = [f"💰 Total balance: {self._fmt(s.get('current_balance', 0))}"]
            for bank, bal in bb.items():
                lines.append(f"  • {bank}: {self._fmt(bal)}")
            return "\n".join(lines)
        return None

    def _cashout(self, q):
        if self._match(q, ['cashout', 'run out', 'how long', 'days left', 'money last', 'broke', 'when will']):
            s = self.d.get('summary', {})
            status = s.get('status', 'SAFE')
            e = '🔴' if status == 'CRITICAL' else '🟡' if status == 'WARNING' else '🟢'
            return (f"{e} Funds last until **{s.get('cashout_date')}** (~{s.get('days_remaining')} days). Status: {status}.")
        return None

    def _burn(self, q):
        if self._match(q, ['burn rate', 'daily spend', 'per day', 'spending per day', 'how much a day']):
            s = self.d.get('summary', {})
            rate = s.get('daily_burn_rate', 0)
            return f"🔥 Daily burn rate: {self._fmt(rate)}\nProjected monthly: {self._fmt(float(rate) * 30)}"
        return None

    def _income(self, q):
        if self._match(q, ['income', 'salary', 'earning', 'credit', 'received', 'earn']):
            s = self.d.get('summary', {})
            return (f"📈 Total income: {self._fmt(s.get('total_income', 0))}\n"
                    f"Monthly surplus: {self._fmt(s.get('monthly_surplus', 0))}")
        return None

    def _anomalies(self, q):
        if self._match(q, ['anomal', 'unusual', 'suspicious', 'weird', 'strange', 'outlier', 'spike']):
            items = self.d.get('anomalies', [])
            if not items:
                return "✅ No unusual transactions detected!"
            lines = [f"⚠️ {len(items)} unusual transaction(s):"]
            for a in items[:4]:
                lines.append(f"  • {a.get('date')} — {a.get('description')}: {self._fmt(a.get('amount', 0))}")
            if len(items) > 4:
                lines.append(f"  ...and {len(items) - 4} more.")
            return "\n".join(lines)
        return None

    def _health(self, q):
        if self._match(q, ['health', 'score', 'how am i doing', 'financial health', 'performance']):
            h = self.d.get('health_score', {})
            score = h.get('overall', h.get('score', 'N/A'))
            label = h.get('label', '')
            try:
                e = '🟢' if float(score) >= 70 else '🟡' if float(score) >= 40 else '🔴'
            except Exception:
                e = '⚪'
            return f"{e} Health score: {score}/100 — {label}"
        return None

    def _category(self, q):
        cat_map = {
            'food': ['food', 'dining', 'restaurant', 'eating', 'grocery', 'swiggy', 'zomato'],
            'entertainment': ['entertainment', 'movie', 'netflix', 'streaming', 'hotstar'],
            'transport': ['transport', 'travel', 'uber', 'ola', 'fuel', 'petrol'],
            'shopping': ['shopping', 'amazon', 'flipkart', 'myntra', 'clothes'],
            'health': ['medical', 'medicine', 'doctor', 'hospital', 'pharmacy'],
            'utilities': ['utility', 'electricity', 'bill', 'recharge', 'internet'],
            'emi': ['emi', 'loan', 'installment'],
        }
        spending = self.d.get('spending_by_category', {})
        total = self.d.get('summary', {}).get('total_spending', 1) or 1
        for cat_key, keywords in cat_map.items():
            if self._match(q, keywords):
                for cat_name, amount in spending.items():
                    if cat_key in cat_name.lower() or any(k in cat_name.lower() for k in keywords[:2]):
                        pct = round(float(amount) / float(total) * 100, 1)
                        return f"📊 {cat_name}: {self._fmt(amount)} ({pct}% of total spending)."
                return f"No spending found under '{cat_key}'."
        return None

    def _leaks(self, q):
        if self._match(q, ['top spend', 'biggest', 'most spent', 'where am i spending', 'highest', 'where money', 'leak', 'largest']):
            leaks = self.d.get('top_leaks', [])
            if not leaks:
                return "No spending data yet."
            lines = ["💸 Top spending categories:"]
            for lk in leaks[:5]:
                lines.append(f"  • {lk['category']}: {self._fmt(lk['amount'])} ({lk['percent_of_spending']}%)")
            return "\n".join(lines)
        return None

    def _recs(self, q):
        if self._match(q, ['recommend', 'suggestion', 'tip', 'save', 'saving', 'advice', 'cut down', 'improve']):
            recs = self.d.get('recommendations', [])
            if not recs:
                return "No recommendations yet. Upload more data!"
            lines = ["💡 Recommendations:"]
            for r in recs[:4]:
                text = r.get('text') or r.get('message') or r.get('description') or r.get('title') or str(r)
                lines.append(f"  • {text}")
            return "\n".join(lines)
        return None

    def _recurring(self, q):
        if self._match(q, ['recurring', 'subscription', 'monthly bill', 'regular']):
            bills = self.d.get('recurring_bills', [])
            if not bills:
                return "No recurring bills detected yet."
            lines = [f"🔄 {len(bills)} recurring charge(s):"]
            for b in bills[:5]:
                name = b.get('description') or b.get('merchant') or b.get('name') or 'Unknown'
                lines.append(f"  • {name}: {self._fmt(b.get('amount', 0))}/month")
            return "\n".join(lines)
        return None

    def _banks(self, q):
        if self._match(q, ['bank', 'account', 'connected', 'which bank']):
            banks = self.d.get('connected_banks', [])
            bb = self.d.get('bank_balances', {})
            if not banks:
                return "No banks connected. Upload a statement to get started."
            lines = [f"🏦 {len(banks)} bank(s):"]
            for b in banks:
                lines.append(f"  • {b}: {self._fmt(bb.get(b, 0))}")
            return "\n".join(lines)
        return None

    def _dow(self, q):
        if self._match(q, ['peak day', 'which day', 'day of week', 'when do i spend', 'busiest day']):
            dow = self.d.get('day_of_week_profile', {})
            peak = dow.get('peak_day', 'N/A')
            amt = dow.get('average_peak_spend', 0)
            series = dow.get('series', {})
            lines = [f"📅 Peak day: {peak} (avg {self._fmt(amt)})"]
            if series:
                mx = max(series.values()) or 1
                for day, val in series.items():
                    bar = '█' * max(1, int(float(val) / mx * 8))
                    lines.append(f"  {day[:3]}: {bar} {self._fmt(val)}")
            return "\n".join(lines)
        return None

    def _goals(self, q):
        if self._match(q, ['goal', 'target', 'saving goal', 'progress', 'how far']):
            goals = self.d.get('goals', [])
            if not goals:
                return "No savings goals set yet. Click 'Set as Goal' on any recommendation!"
            lines = ["🎯 Savings goals:"]
            for g in goals:
                lines.append(f"  • {g['name']}: {g['progress']}% — {g['eta_months']} month(s) to ₹{g['target']:.0f} by {g['deadline']}")
            return "\n".join(lines)
        return None

    def _invest(self, q):
        if self._match(q, ['invest', 'investment', 'mutual fund', 'sip', 'grow money', 'portfolio']):
            inv = self.d.get('investments', {})
            if not inv:
                return "Upload more data for investment recommendations."
            surplus = inv.get('monthly_investable', 0)
            recs = inv.get('recommendations', [])
            lines = [f"📈 Monthly investable surplus: {self._fmt(surplus)}"]
            for r in recs[:4]:
                name = r.get('name') or r.get('type') or str(r)
                lines.append(f"  • {name}: {self._fmt(r.get('amount', 0))}/month")
            return "\n".join(lines)
        return None

    def _help(self, q):
        return ("🤖 ForeCashy AI can help with:\n"
                "  • 'What's my balance?'\n"
                "  • 'Can I take a loan?'\n"
                "  • 'Find transaction for Amazon'\n"
                "  • 'When will I run out of money?'\n"
                "  • 'Health score?'\n"
                "  • 'Show my recommendations'\n"
                "  • 'Recurring bills?'\n"
                "  • 'Which day do I spend the most?'")
