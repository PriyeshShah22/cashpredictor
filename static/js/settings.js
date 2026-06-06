const toastRoot = document.getElementById('toast-stack');

function pushToast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  toastRoot.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

async function loadSettings() {
  feather.replace();

  try {
    const [profileResponse, analysisResponse] = await Promise.all([
      fetch('/api/profile'),
      fetch('/api/analyze')
    ]);

    if (!profileResponse.ok) {
      window.location.href = '/';
      return;
    }

    const profileData = await profileResponse.json();
    const analysisData = await analysisResponse.json();
    const user = profileData.user || {};

    document.getElementById('profile-name').value = user.full_name || '';
    document.getElementById('profile-email').value = user.email || '';
    document.getElementById('alert-email-note').textContent = user.email
      ? `Financial alerts will be delivered to ${user.email}`
      : 'Financial alerts will be delivered to your account email';

    const saved = JSON.parse(localStorage.getItem('cashforecast_settings') || '{}');
    document.getElementById('toggle-anomaly').checked = saved.anomaly ?? true;
    document.getElementById('toggle-digest').checked = saved.digest ?? true;

    const banks = analysisData.connected_banks || [];
    document.getElementById('connected-banks-list').innerHTML = banks.length
      ? banks.map((bank) => `
        <div class="setting-row"><span>${bank}</span><span class="pill">Connected</span></div>
      `).join('')
      : '<div class="empty-state">No bank data uploaded yet. Use demo mode or upload a statement.</div>';
  } catch (error) {
    console.error(error);
    pushToast('Unable to load settings', 'error');
  }
}

document.getElementById('save-settings')?.addEventListener('click', async () => {
  const payload = {
    full_name: document.getElementById('profile-name').value.trim(),
    email: document.getElementById('profile-email').value.trim(),
    anomaly: document.getElementById('toggle-anomaly').checked,
    digest: document.getElementById('toggle-digest').checked
  };

  try {
    const response = await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || 'Could not save settings');
    }

    localStorage.setItem('cashforecast_settings', JSON.stringify({
      anomaly: payload.anomaly,
      digest: payload.digest
    }));

    document.getElementById('alert-email-note').textContent = `Financial alerts will be delivered to ${data.user.email}`;
    pushToast(data.message || 'Preferences saved', 'success');
  } catch (error) {
    pushToast(error.message || 'Could not save settings', 'error');
  }
});

document.getElementById('reset-data')?.addEventListener('click', async () => {
  try {
    const response = await fetch('/api/reset', { method: 'POST' });
    if (!response.ok) {
      throw new Error('Reset failed');
    }
    pushToast('Workspace reset to demo mode', 'warning');
    setTimeout(() => { window.location.href = '/dashboard.html'; }, 700);
  } catch (error) {
    pushToast(error.message || 'Reset failed', 'error');
  }
});

window.addEventListener('DOMContentLoaded', loadSettings);
