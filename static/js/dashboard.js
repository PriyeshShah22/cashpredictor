const BANK_COLORS = {
  all: '#3b82f6',
  HDFC: '#e63946',
  SBI: '#2196f3',
  ICICI: '#ff6d00',
  Axis: '#7b2d8b',
  Kotak: '#e91e63',
  Yes: '#00897b',
  Other: '#3b82f6'
};

let activeBankFilter = 'all';
let dashboardState = null;
let charts = {};
const toastStack = document.getElementById('toast-stack');

function currency(value) {
  return `₹${Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

function showToast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  toastStack.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function animateBars() {
  setTimeout(() => {
    document.querySelectorAll('.cf-progress-fill').forEach((bar) => {
      bar.style.width = `${bar.dataset.target}%`;
    });
  }, 300);
}

function setRing(el, percent, color) {
  const circleLength = 2 * Math.PI * 46;
  el.style.strokeDasharray = circleLength;
  el.style.strokeDashoffset = circleLength - (Math.max(0, Math.min(percent, 100)) / 100) * circleLength;
  el.style.stroke = color;
}

function renderBankSwitcher(data) {
  const container = document.getElementById('bank-switcher');
  const banks = [{ name: 'all', label: 'All Banks', balance: Object.values(data.bank_balances).reduce((a, b) => a + b, 0) }]
    .concat(Object.entries(data.bank_balances).map(([name, balance]) => ({ name, label: name, balance })));
  container.innerHTML = banks.map((bank) => `
    <button class="bank-pill ${bank.name === activeBankFilter ? 'active' : ''}" data-bank="${bank.name}" style="--bank-color:${BANK_COLORS[bank.name] || BANK_COLORS.Other}">
      <div style="font-size:0.8rem; color:var(--text-secondary);">${bank.label}</div>
      <strong class="bank-balance" data-value="${bank.balance}">${currency(bank.balance)}</strong>
    </button>
  `).join('');
  container.querySelectorAll('.bank-pill').forEach((pill) => pill.addEventListener('click', () => switchBank(pill.dataset.bank)));
}

async function switchBank(bank) {
  activeBankFilter = bank;
  await loadDashboard(bank);
}

function renderSummary(summary) {
  const delta = summary.comparison_deltas || {};
  const cards = [
    ['Current Balance', currency(summary.current_balance), delta.current_balance],
    ['Total Income', currency(summary.total_income), delta.total_income],
    ['Total Spending', currency(summary.total_spending), delta.total_spending],
    ['Daily Burn Rate', currency(summary.daily_burn_rate), delta.daily_burn_rate]
  ];
  document.getElementById('summary-grid').innerHTML = cards.map(([label, value, change]) => `
    <div class="glass-card summary-card">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${value}</div>
      <div class="metric-delta">${change >= 0 ? '↑' : '↓'} ${Math.abs(change || 0)}% vs previous month</div>
    </div>
  `).join('');
}

function renderCountdown(summary) {
  const color = summary.days_remaining > 30 ? '#10b981' : summary.days_remaining >= 7 ? '#f59e0b' : '#ef4444';
  
  let daysText = `${summary.days_remaining.toLocaleString('en-IN')} days`;
  let dateText = summary.cashout_date;
  
  if (summary.days_remaining >= 999999) {
    daysText = 'Safe — Not running out of cash';
    dateText = 'Growing balance';
  } else if (summary.days_remaining > 365) {
    const years = (summary.days_remaining / 365).toFixed(1);
    daysText = `~${years} Years`;
  }

  document.getElementById('days-remaining').textContent = daysText;
  document.getElementById('cashout-date').textContent = dateText;
  document.getElementById('cashout-trend').textContent = summary.status === 'SAFE' ? 'Runway is improving compared with the recent trend.' : summary.status === 'WARNING' ? 'Monitor burn rate closely over the next 2 weeks.' : 'Cash-out risk is accelerating — immediate action recommended.';
  setRing(document.getElementById('cashout-ring'), Math.min(summary.days_remaining, 60) / 60 * 100, color);
}

function renderHealth(health) {
  document.getElementById('health-overall').textContent = health.overall;
  const color = health.overall >= 71 ? '#10b981' : health.overall >= 41 ? '#f59e0b' : '#ef4444';
  setRing(document.getElementById('health-ring'), health.overall, color);
  const items = [
    ['Spending Control', health.spending_control],
    ['Savings Habit', health.savings_habit],
    ['Bill Regularity', health.bill_regularity]
  ];
  document.getElementById('health-bars').innerHTML = items.map(([label, value]) => `
    <div>
      <div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;"><span>${label}</span><span>${value}%</span></div>
      <div class="cf-progress-track"><div class="cf-progress-fill ${value < 40 ? 'danger' : value < 70 ? 'warning' : 'success'}" data-target="${value}"></div></div>
    </div>
  `).join('');
}

function destroyIfExists(name) {
  if (charts[name]) charts[name].destroy();
}

function renderCategoryChart(spending) {
  const labels = Object.keys(spending);
  const values = Object.values(spending);
  const ctx = document.getElementById('category-chart');
  destroyIfExists('category');
  charts.category = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#14b8a6','#f472b6','#94a3b8'] }] },
    options: { plugins: { legend: { display: false } } }
  });
  const max = Math.max(...values, 1);
  document.getElementById('category-bars').innerHTML = labels.map((label, index) => `
    <div>
      <div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;"><span>${label}</span><span>${currency(values[index])}</span></div>
      <div class="cf-progress-track"><div class="cf-progress-fill" data-target="${(values[index] / max) * 100}"></div></div>
    </div>
  `).join('');
}

function renderWeeklyChart(weekly) {
  destroyIfExists('weekly');
  charts.weekly = new Chart(document.getElementById('weekly-chart'), {
    type: 'bar',
    data: { labels: weekly.labels, datasets: [{ label: 'Weekly spending', data: weekly.values, borderRadius: 10, backgroundColor: '#3b82f6' }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { ticks: { color: '#94a3b8' } }, x: { ticks: { color: '#94a3b8' } } } }
  });
}

function renderForecastChart(forecast) {
  destroyIfExists('forecast');
  document.getElementById('forecast-model').textContent = `${forecast.model_used} • ${Math.round(forecast.confidence * 100)}% confidence`;
  const hist = forecast.historical || [];
  const pred = forecast.predicted || [];
  charts.forecast = new Chart(document.getElementById('forecast-chart'), {
    type: 'line',
    data: {
      labels: [...hist.map((d) => d.date), ...pred.map((d) => d.date)],
      datasets: [
        { label: 'Historical', data: [...hist.map((d) => d.balance), ...new Array(pred.length).fill(null)], borderColor: '#3b82f6', tension: 0.35 },
        { label: 'AI Forecast', data: [...new Array(hist.length).fill(null), ...pred.map((d) => d.balance)], borderColor: '#8b5cf6', borderDash: [8, 6], tension: 0.35 },
        { label: 'Lower', data: [...new Array(hist.length).fill(null), ...pred.map((d) => d.lower)], borderColor: 'rgba(139,92,246,0.12)', pointRadius: 0 },
        { label: 'Upper', data: [...new Array(hist.length).fill(null), ...pred.map((d) => d.upper)], borderColor: 'rgba(139,92,246,0.12)', pointRadius: 0, fill: '-1', backgroundColor: 'rgba(139,92,246,0.12)' },
        { label: '₹0 threshold', data: new Array(hist.length + pred.length).fill(0), borderColor: '#ef4444', borderDash: [4, 4], pointRadius: 0 }
      ]
    },
    options: { interaction: { mode: 'index', intersect: false }, scales: { y: { ticks: { color: '#94a3b8' } }, x: { display: false } } }
  });
}

function renderAnomalies(anomalies) {
  document.getElementById('anomaly-count').textContent = `${anomalies.length} anomalies`;
  const list = document.getElementById('anomaly-list');
  if (!anomalies.length) {
    list.innerHTML = '<div class="empty-state">✅ All transactions look normal. No unusual spending detected.</div>';
    return;
  }
  list.innerHTML = anomalies.map((item) => `
    <div class="list-item">
      <div>
        <div style="display:flex; align-items:center; gap:0.6rem; flex-wrap:wrap;">
          <strong>${item.description}</strong>
          <span class="badge ${item.severity === 'HIGH' ? 'red' : 'amber'}">${item.severity}</span>
        </div>
        <div class="text-muted" style="margin-top:0.35rem;">${item.date} • ${item.bank} • ${item.message}</div>
      </div>
      <div style="text-align:right; display:grid; gap:0.55rem; align-content:start;">
        <strong>${currency(item.amount)}</strong>
        <button class="ghost-btn" onclick="dismissAnomaly('${item.id}')">Mark as expected</button>
      </div>
    </div>
  `).join('');
}

async function dismissAnomaly(id) {
  await fetch('/api/dismiss_anomaly', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ anomaly_id: id }) });
  showToast('Anomaly dismissed', 'info');
  loadDashboard(activeBankFilter);
}
window.dismissAnomaly = dismissAnomaly;

function renderRecommendations(recommendations) {
  const list = document.getElementById('recommendation-list');
  if (!recommendations.length) {
    list.innerHTML = '<div class="empty-state">🎯 Your finances look optimized! Nothing to suggest right now.</div>';
    return;
  }
  list.innerHTML = recommendations.map((item) => `
    <div class="list-item">
      <div>
        <strong>${item.title}</strong>
        <div class="text-muted" style="margin-top:0.35rem;">${item.description}</div>
      </div>
      <div style="text-align:right;">
        <strong>${currency(item.monthly_saving)}/mo</strong>
      </div>
    </div>
  `).join('');
}


function renderRecurring(recurring) {
  const list = document.getElementById('recurring-list');
  if (!recurring.length) {
    list.innerHTML = '<div class="empty-state">📄 No recurring patterns found yet.</div>';
    return;
  }
  list.innerHTML = recurring.map((item) => `
    <div class="list-item">
      <div>
        <strong>${item.merchant}</strong>
        <div class="text-muted" style="margin-top:0.35rem;">${item.frequency} • Next expected ${item.next_expected_date} • ${item.bank}</div>
      </div>
      <div style="text-align:right;">
        <strong>${currency(item.annual_cost)}/yr</strong>
      </div>
    </div>
  `).join('');
}

function renderNetScore(netScore) {
  const container = document.getElementById('net-score-grid');
  container.innerHTML = netScore.map((item) => `
    <div class="glass-card" style="padding:0.9rem; text-align:center; border-color:${item.positive ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'};">      <div style="width:16px; height:16px; border-radius:5px; margin:0 auto 0.6rem; background:${item.positive ? '#10b981' : '#ef4444'};"></div>
      <div style="font-size:0.85rem;">${item.month}</div>
      <div class="text-muted" style="font-size:0.8rem; margin-top:0.3rem;">${currency(item.net)}</div>
    </div>
  `).join('');
}


function renderDayProfile(profile) {
  document.getElementById('dow-insight').textContent = `You spend the most on ${profile.peak_day}s (avg ${currency(profile.average_peak_spend)}).`;
  const max = Math.max(...Object.values(profile.series), 1);
  document.getElementById('dow-bars').innerHTML = Object.entries(profile.series).map(([day, value]) => `
    <div>
      <div style="display:flex; justify-content:space-between; margin-bottom:0.35rem;"><span>${day.slice(0,3)}</span><span>${currency(value)}</span></div>
      <div class="cf-progress-track"><div class="cf-progress-fill ${day === profile.peak_day ? 'warning' : ''}" data-target="${(value / max) * 100}"></div></div>
    </div>
  `).join('');
}

function renderAutonomousAlert(alertState) {
  const panel = document.getElementById('autonomous-alert-panel');
  const title = document.getElementById('autonomous-alert-title');
  const badge = document.getElementById('autonomous-alert-badge');
  const body = document.getElementById('autonomous-alert-body');

  if (!alertState || !alertState.triggered || !alertState.top_alert) {
    panel.style.display = 'none';
    return;
  }

  panel.style.display = 'block';
  const alert = alertState.top_alert;
  const statusMap = {
    sent: 'Email sent',
    demo_console: 'Demo console',
    suppressed_duplicate: 'Already notified',
    error_fallback: 'Console fallback'
  };
  title.textContent = `${alert.label} is rising across the last 3 cycles`;
  badge.textContent = statusMap[alertState.email_status] || 'Triggered';
  body.textContent = `Increase: ${alert.percentage_increase}% • Estimated impact: ${currency(alert.estimated_monthly_impact)} • Suggested action: ${alert.suggested_action}`;
}

function renderTransactions(transactions) {
  const body = document.getElementById('transaction-body');
  const items = transactions.slice(0, 12);
  if (!items.length) {
    body.innerHTML = '<tr><td colspan="6"><div class="empty-state">📂 No transactions found. Try adjusting your filters.</div></td></tr>';
    return;
  }
  body.innerHTML = items.map((item) => `
    <tr>
      <td>${item.date}</td>
      <td>${item.bank}</td>
      <td>${item.description}</td>
      <td>${item.category}</td>
      <td style="color:${item.amount < 0 ? '#fca5a5' : '#86efac'}">${currency(item.amount)}</td>
      <td>${currency(item.balance)}</td>
    </tr>
  `).join('');
}

async function loadDashboard(bank = 'all') {
  document.querySelectorAll('.bank-pill').forEach((pill) => pill.classList.toggle('active', pill.dataset.bank === bank));
  const endpoint = bank && bank !== 'all' ? `/api/analyze?bank=${encodeURIComponent(bank)}` : '/api/analyze';
  const response = await fetch(endpoint);
  dashboardState = await response.json();
  renderBankSwitcher(dashboardState);
  renderSummary(dashboardState.summary);
  renderCountdown(dashboardState.summary);
  renderHealth(dashboardState.health_score);
  renderCategoryChart(dashboardState.spending_by_category);
  renderWeeklyChart(dashboardState.weekly_spending);
  renderForecastChart(dashboardState.forecast);
  renderAnomalies(dashboardState.anomalies);
  renderRecommendations(dashboardState.recommendations);
  renderRecurring(dashboardState.recurring_bills);
  renderTransactions(dashboardState.transactions);
  renderDayProfile(dashboardState.day_of_week_profile);
  renderNetScore(dashboardState.net_score);
  renderAutonomousAlert(dashboardState.autonomous_alert);
  document.getElementById('demo-banner').style.display = dashboardState.demo_mode ? 'block' : 'none';
  document.getElementById('demo-banner').textContent = 'Demo Mode — Upload your own bank statement to get personalized insights';
  const autonomousCount = dashboardState.autonomous_alert && dashboardState.autonomous_alert.triggered ? 1 : 0;
  document.getElementById('notif-pill').textContent = `${dashboardState.anomalies.length + dashboardState.recommendations.length + autonomousCount} new alerts`;
  animateBars();
  feather.replace();
}

async function initUser() {
  try {
    const res = await fetch('/api/user');
    const data = await res.json();
    if (data.status === 'success') {
      const name = data.user.full_name || data.user.email.split('@')[0];
      document.getElementById('user-display').textContent = data.user.email;
      document.getElementById('welcome-msg').textContent = `Welcome back, ${name}`;
    } else {
      window.location.href = '/';
    }
  } catch (err) {
    window.location.href = '/';
  }
}

document.getElementById('logout-btn')?.addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/';
});

window.addEventListener('DOMContentLoaded', () => {
  feather.replace();
  initUser();
  loadDashboard();
});
