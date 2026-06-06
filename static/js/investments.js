let allocationChart;
let sipChart;
const toastRoot = document.getElementById('toast-stack');

function money(value) {
  return `₹${Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

function toast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  toastRoot.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function barMarkup(label, value, max, cls = '') {
  return `
    <div>
      <div style="display:flex; justify-content:space-between; margin-bottom:0.35rem;"><span>${label}</span><span>${money(value)}</span></div>
      <div class="cf-progress-track"><div class="cf-progress-fill ${cls}" data-target="${(value / Math.max(max, 1)) * 100}"></div></div>
    </div>
  `;
}

function animateBars() {
  setTimeout(() => {
    document.querySelectorAll('.cf-progress-fill').forEach((bar) => { bar.style.width = `${bar.dataset.target}%`; });
  }, 250);
}

async function loadInvestmentData() {
  const response = await fetch('/api/analyze');
  const data = await response.json();
  feather.replace();

  const summaryCards = [
    ['Liquid Balance', money(data.summary.current_balance)],
    ['Monthly Surplus', money(data.summary.monthly_surplus)],
    ['Investable This Month', money(data.investments.monthly_investable)],
    ['Suggested SIP', money(data.investments.sip_recommendation)]
  ];
  document.getElementById('invest-summary').innerHTML = summaryCards.map(([label, value]) => `
    <div class="glass-card summary-card"><div class="metric-label">${label}</div><div class="metric-value">${value}</div></div>
  `).join('');

  const allocation = data.investments.allocation;
  const labels = Object.keys(allocation);
  const values = labels.map((key) => allocation[key].amount);
  const totalAmount = values.reduce((a, b) => a + b, 0);

  if (allocationChart) allocationChart.destroy();
  
  const ctx = document.getElementById('allocation-chart');
  const list = document.getElementById('allocation-list');

  if (totalAmount <= 0) {
    // If no surplus, show the Target Percentages instead of amounts
    const targetValues = labels.map((key) => allocation[key].percent);
    allocationChart = new Chart(ctx, {
      type: 'doughnut',
      data: { 
        labels, 
        datasets: [{ 
          data: targetValues, 
          backgroundColor: ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#14b8a6'],
          borderWidth: 0
        }] 
      },
      options: { 
        plugins: { 
          legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } },
          tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.raw}% (Target)` } }
        },
        cutout: '70%'
      }
    });
    list.innerHTML = `
      <div class="glass-card" style="padding:1rem; border-color:var(--warning); margin-bottom:1rem;">
        <div class="text-muted" style="font-size:0.85rem;">⚠️ No monthly surplus detected. Showing <strong>Target Allocation</strong> for when you have investable cash.</div>
      </div>
    ` + labels.map((key) => `
      <div class="list-item">
        <div><strong>${key}</strong><div class="text-muted">${allocation[key].percent}% target</div></div>
        <span class="badge">Target</span>
      </div>
    `).join('');
  } else {
    allocationChart = new Chart(ctx, {
      type: 'pie',
      data: { labels, datasets: [{ data: values, backgroundColor: ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#14b8a6'] }] },
      options: { plugins: { legend: { labels: { color: '#fff' } } } }
    });
    list.innerHTML = labels.map((key) => `
      <div class="list-item"><div><strong>${key}</strong><div class="text-muted">${allocation[key].percent}% allocation</div></div><strong>${money(allocation[key].amount)}</strong></div>
    `).join('');
  }

  const split = data.investments.save_vs_invest;
  document.getElementById('surplus-breakdown').innerHTML = [
    barMarkup('Save', split.save, data.investments.monthly_investable, 'success'),
    barMarkup('Invest', split.invest, data.investments.monthly_investable),
    barMarkup('Keep Liquid', split.keep_liquid, data.investments.monthly_investable, 'warning')
  ].join('');

  if (sipChart) sipChart.destroy();
  sipChart = new Chart(document.getElementById('sip-chart'), {
    type: 'line',
    data: { labels: data.investments.sip_projection.map((item) => `${item.year}Y`), datasets: [{ label: 'Projected value', data: data.investments.sip_projection.map((item) => item.value), borderColor: '#10b981', tension: 0.35 }] },
    options: { plugins: { legend: { labels: { color: '#fff' } } }, scales: { y: { ticks: { color: '#94a3b8' } }, x: { ticks: { color: '#94a3b8' } } } }
  });

  const goals = data.goals || [];
  const goalList = document.getElementById('goal-list');
  goalList.innerHTML = goals.length ? goals.map((goal) => `
    <div class="goal-card">
      <div>
        <strong>${goal.name}</strong>
        <div class="text-muted">Target ${money(goal.target)} by ${goal.deadline}</div>
        <div class="cf-progress-track" style="margin-top:0.6rem;"><div class="cf-progress-fill ${goal.progress < 40 ? 'danger' : goal.progress < 70 ? 'warning' : 'success'}" data-target="${goal.progress}"></div></div>
      </div>
      <div style="text-align:right;">
        <strong>${goal.progress}%</strong>
        <div class="text-muted">ETA ${goal.eta_months} months</div>
      </div>
    </div>
  `).join('') : '<div class="empty-state">🎯 Add a goal to start tracking your pace.</div>';

  const bankBalances = Object.values(data.bank_balances);
  const maxBank = Math.max(...bankBalances, 1);
  document.getElementById('bank-balance-bars').innerHTML = Object.entries(data.bank_balances).map(([bank, value]) => barMarkup(bank, value, maxBank)).join('');

  const budgets = {
    Food: data.summary.total_income * 0.15,
    Shopping: data.summary.total_income * 0.12,
    Entertainment: data.summary.total_income * 0.08,
    Subscriptions: data.summary.total_income * 0.03
  };
  document.getElementById('budget-bars').innerHTML = Object.entries(budgets).map(([key, budget]) => {
    const actual = data.spending_by_category[key] || 0;
    const cls = actual > budget ? 'danger' : 'success';
    return `
      <div>
        <div style="display:flex; justify-content:space-between; margin-bottom:0.35rem;"><span>${key}</span><span>${money(actual)} / ${money(budget)}</span></div>
        <div class="cf-progress-track"><div class="cf-progress-fill ${cls}" data-target="${(actual / Math.max(budget, 1)) * 100}"></div></div>
      </div>
    `;
  }).join('');
  animateBars();
}

document.getElementById('goal-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    name: document.getElementById('goal-name').value,
    target: document.getElementById('goal-target').value,
    deadline: document.getElementById('goal-deadline').value
  };
  const response = await fetch('/api/set_goal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (response.ok) {
    toast('Goal saved successfully', 'success');
    event.target.reset();
    loadInvestmentData();
  } else {
    toast('Could not save goal', 'error');
  }
});

window.addEventListener('DOMContentLoaded', loadInvestmentData);
