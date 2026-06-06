let transactionState = [];
let currentPage = 1;
const pageSize = 25;

function formatMoney(value) {
  return `₹${Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

async function loadTransactions() {
  const response = await fetch('/api/analyze');
  const data = await response.json();
  transactionState = data.transactions;
  feather.replace();
  populateFilters(data);
  applyFilters();
}

function populateFilters(data) {
  const bankFilter = document.getElementById('bank-filter');
  bankFilter.innerHTML = '<option value="">All banks</option>' + data.connected_banks.map((bank) => `<option value="${bank}">${bank}</option>`).join('');
  const categories = [...new Set(data.transactions.map((item) => item.category))].sort();
  document.getElementById('category-filter').innerHTML = '<option value="">All categories</option>' + categories.map((cat) => `<option value="${cat}">${cat}</option>`).join('');
}

function filteredTransactions() {
  const search = document.getElementById('search-input').value.toLowerCase();
  const bank = document.getElementById('bank-filter').value;
  const category = document.getElementById('category-filter').value;
  const minAmount = Number(document.getElementById('min-amount').value || 0);
  const maxAmount = Number(document.getElementById('max-amount').value || 999999999);
  const anomalyOnly = document.getElementById('anomaly-only').checked;
  return transactionState.filter((item) => {
    const matchesSearch = !search || item.description.toLowerCase().includes(search) || item.category.toLowerCase().includes(search);
    const matchesBank = !bank || item.bank === bank;
    const matchesCategory = !category || item.category === category;
    const amountAbs = Math.abs(item.amount);
    const matchesAmount = amountAbs >= minAmount && amountAbs <= maxAmount;
    const matchesAnomaly = !anomalyOnly || item.is_anomaly;
    return matchesSearch && matchesBank && matchesCategory && matchesAmount && matchesAnomaly;
  });
}

function applyFilters() {
  const rows = filteredTransactions();
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  currentPage = Math.min(currentPage, totalPages);
  const pageRows = rows.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const body = document.getElementById('txn-table-body');
  body.innerHTML = pageRows.length ? pageRows.map((item) => `
    <tr>
      <td>${item.date}</td>
      <td>${item.bank}</td>
      <td>${item.description}</td>
      <td><span class="pill">${item.category}</span></td>
      <td style="color:${item.amount < 0 ? '#fca5a5' : '#86efac'}">${formatMoney(item.amount)}</td>
      <td>${formatMoney(item.balance)}</td>
      <td>${item.is_anomaly ? '<span class="badge red">Flagged</span>' : '<span class="badge green">Clear</span>'}</td>
    </tr>
  `).join('') : '<tr><td colspan="7"><div class="empty-state">📂 No transactions found. Try adjusting your filters.</div></td></tr>';
  document.getElementById('pagination-label').textContent = `Page ${currentPage} of ${totalPages}`;
}

['search-input', 'bank-filter', 'category-filter', 'min-amount', 'max-amount', 'anomaly-only'].forEach((id) => {
  document.addEventListener('input', (event) => {
    if (event.target.id === id) {
      currentPage = 1;
      applyFilters();
    }
  });
  document.addEventListener('change', (event) => {
    if (event.target.id === id) {
      currentPage = 1;
      applyFilters();
    }
  });
});

document.getElementById('prev-page')?.addEventListener('click', () => {
  currentPage = Math.max(1, currentPage - 1);
  applyFilters();
});

document.getElementById('next-page')?.addEventListener('click', () => {
  const total = Math.max(1, Math.ceil(filteredTransactions().length / pageSize));
  currentPage = Math.min(total, currentPage + 1);
  applyFilters();
});

document.getElementById('export-btn')?.addEventListener('click', () => {
  const rows = filteredTransactions();
  const header = ['Date', 'Bank', 'Description', 'Category', 'Amount', 'Balance', 'Anomaly'];
  const csv = [header.join(','), ...rows.map((row) => [row.date, row.bank, `"${row.description}"`, row.category, row.amount, row.balance, row.is_anomaly].join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'cashforecast_transactions.csv';
  link.click();
});

window.addEventListener('DOMContentLoaded', async () => {
    await loadTransactions();

    // ── Chatbot Deep-Link: auto-apply ?search=term from URL ──
    const params = new URLSearchParams(window.location.search);
    const searchTerm = params.get('search');
    if (searchTerm) {
        const searchInput = document.getElementById('search-input');
        searchInput.value = searchTerm;
        currentPage = 1;
        applyFilters();

        const firstRow = document.querySelector('#txn-table-body tr');
        if (firstRow) {
            firstRow.style.outline = '2px solid #6366f1';
            firstRow.style.borderRadius = '8px';
            firstRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        const banner = document.createElement('div');
        banner.style.cssText = 'background:rgba(99,102,241,0.15);border:1px solid #6366f1;border-radius:10px;padding:0.75rem 1rem;margin-bottom:1rem;font-size:0.875rem;color:#a5b4fc;';
        banner.innerHTML = `🤖 <strong>ForeCashy navigated you here</strong> — showing results for "<strong>${searchTerm}</strong>"`;
        document.querySelector('.filter-bar').parentElement.prepend(banner);
    }
});
