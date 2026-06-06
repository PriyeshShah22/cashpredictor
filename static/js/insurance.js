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

function riskBadge(level) {
  const map = {
    LOW: 'green',
    MEDIUM: 'amber',
    HIGH: 'red',
    NO_DATA: 'amber'
  };
  return map[level] || 'amber';
}

function renderSummary(insights) {
  const summary = insights.insurance_summary || {};
  const coveredCount = Object.values(summary).filter((item) => item.covered).length;
  const missingCount = (insights.missing_policies || []).length;
  const profile = insights.user_profile || { category_spends: {} };
  const cards = [
    ['Overall Risk Score', `${insights.overall_risk_score || 0}/100`],
    ['Policies Covered', coveredCount],
    ['Policies Missing', missingCount],
    ['Estimated Annual Income', money(profile.estimated_annual_income || 0)]
  ];
  document.getElementById('protection-summary').innerHTML = cards.map(([label, value]) => `
    <div class="glass-card summary-card">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${value}</div>
    </div>
  `).join('');
}

function renderPolicies(insights) {
  const summary = insights.insurance_summary || {};
  const entries = Object.entries(summary);
  const grid = document.getElementById('policy-grid');
  if (!entries.length) {
    grid.innerHTML = '<div class="empty-state">🛡️ No protection insights available yet.</div>';
    return;
  }

  grid.innerHTML = entries.map(([key, item]) => `
    <div class="list-item" style="align-items:flex-start; border-color:${item.covered ? 'rgba(16,185,129,0.22)' : item.gap_level === 'HIGH' ? 'rgba(239,68,68,0.22)' : 'rgba(245,158,11,0.22)'};">
      <div style="display:grid; gap:0.5rem; width:100%;">
        <div style="display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; align-items:center;">
          <div style="display:flex; gap:0.75rem; align-items:center; flex-wrap:wrap;">
            <strong>${item.label}</strong>
            <span class="badge ${riskBadge(item.gap_level)}">${item.covered ? 'Covered' : item.gap_level}</span>
          </div>
          <div class="text-muted">${item.detected_provider ? `Provider: ${item.detected_provider}` : 'No policy detected'}</div>
        </div>
        <div class="text-muted">${item.explanation}</div>
        <div style="display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; margin-top:0.25rem;">
          <span>Avg premium: <strong>${item.average_premium ? money(item.average_premium) : '—'}</strong></span>
          <span>Recommended cover: <strong>${item.recommended_cover_amount ? money(item.recommended_cover_amount) : '—'}</strong></span>
        </div>
        <div class="text-muted">Suggested action: ${item.suggested_action}</div>
      </div>
    </div>
  `).join('');
}

function renderRecommendations(insights) {
  const list = document.getElementById('recommendation-list');
  const recs = insights.recommendations || [];
  if (!recs.length) {
    list.innerHTML = '<div class="empty-state">✅ No urgent protection gaps detected from current transaction history.</div>';
    return;
  }

  list.innerHTML = recs.map((rec) => `
    <div class="list-item">
      <div>
        <div style="display:flex; align-items:center; gap:0.65rem; flex-wrap:wrap;">
          <strong>${rec.label}</strong>
          <span class="badge ${riskBadge(rec.gap_level)}">${rec.gap_level}</span>
        </div>
        <div class="text-muted" style="margin-top:0.35rem;">${rec.explanation}</div>
      </div>
      <div style="text-align:right; display:grid; gap:0.35rem; align-content:start;">
        <strong>${rec.recommended_cover_amount ? money(rec.recommended_cover_amount) : 'Review'}</strong>
        <div class="text-muted" style="max-width:14rem;">${rec.suggested_action}</div>
      </div>
    </div>
  `).join('');
}

function renderProfile(insights) {
  const profile = insights.user_profile || { category_spends: {} };
  const spends = profile.category_spends || {};
  const items = [
    ['Estimated monthly income', money(profile.estimated_monthly_income || 0)],
    ['Family size proxy', profile.family_size_proxy || 0],
    ['Medical spend', money(spends.medical || 0)],
    ['Travel spend', money(spends.travel || 0)],
    ['Fuel spend', money(spends.fuel || 0)],
    ['Rent spend', money(spends.rent || 0)]
  ];
  document.getElementById('profile-metrics').innerHTML = items.map(([label, value]) => `
    <div class="list-item"><span>${label}</span><strong>${value}</strong></div>
  `).join('');
}

function renderMissing(insights) {
  const items = insights.missing_policies || [];
  const list = document.getElementById('missing-list');
  if (!items.length) {
    list.innerHTML = '<div class="empty-state">🧾 Nothing critical is missing based on current signals.</div>';
    return;
  }

  list.innerHTML = items.map((item, index) => `
    <div class="list-item">
      <div>
        <strong>${index + 1}. ${item.charAt(0).toUpperCase() + item.slice(1)} protection gap</strong>
        <div class="text-muted" style="margin-top:0.35rem;">This policy type is not detected in your transaction history.</div>
      </div>
    </div>
  `).join('');
}

async function loadProtection() {
  try {
    const response = await fetch('/api/analyze');
    if (!response.ok) {
      window.location.href = '/';
      return;
    }
    const data = await response.json();
    feather.replace();
    const insights = data.insurance_insights || {};
    renderSummary(insights);
    renderPolicies(insights);
    renderRecommendations(insights);
    renderProfile(insights);
    renderMissing(insights);
    if (insights.message) {
      document.getElementById('protection-subtitle').textContent = insights.message;
      toast(insights.message, 'info');
    }
  } catch (error) {
    toast('Could not load protection insights', 'error');
  }
}

window.addEventListener('DOMContentLoaded', loadProtection);
