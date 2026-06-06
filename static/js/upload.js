const slots = [...document.querySelectorAll('.upload-slot')];
const analyzeBtn = document.getElementById('analyze-btn');
const selectedFiles = new Map();
const toastStack = document.getElementById('toast-stack');

function showToast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  toastStack.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function updateButtonState() {
  analyzeBtn.disabled = selectedFiles.size === 0;
}

slots.forEach((slot) => {
  const input = slot.querySelector('input[type="file"]');
  const status = slot.querySelector('.file-status');
  const progress = slot.querySelector('.upload-progress span');
  const bank = slot.dataset.bank;
  const dropZone = slot.querySelector('.drop-zone');

  function handleFile(file) {
    if (!file) return;
    selectedFiles.set(bank, file);
    status.textContent = `${file.name} selected`;
    progress.style.width = '100%';
    showToast(`✅ ${bank} statement ready`, 'success');
    updateButtonState();
  }

  input.addEventListener('change', (event) => handleFile(event.target.files[0]));
  ['dragenter', 'dragover'].forEach((evt) => dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    slot.style.borderColor = 'rgba(59,130,246,0.5)';
  }));
  ['dragleave', 'drop'].forEach((evt) => dropZone.addEventListener(evt, () => {
    slot.style.borderColor = 'rgba(255,255,255,0.14)';
  }));
  dropZone.addEventListener('drop', (event) => {
    event.preventDefault();
    handleFile(event.dataTransfer.files[0]);
  });
});

analyzeBtn?.addEventListener('click', async () => {
  if (selectedFiles.size === 0) {
    window.location.href = '/dashboard.html';
    return;
  }
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = 'Analyzing...';
  const formData = new FormData();
  [...selectedFiles.entries()].forEach(([bank, file], index) => {
    formData.append('files', file);
    formData.append(`bank_${index}`, bank);
  });
  try {
    const response = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'Upload failed');
    localStorage.setItem('cashforecast_upload_meta', JSON.stringify(data));
    showToast('💡 Statements uploaded successfully', 'success');
    setTimeout(() => { window.location.href = '/dashboard.html'; }, 700);
  } catch (error) {
    showToast(`❌ Upload failed: ${error.message}`, 'error');
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = 'Analyze My Finances';
  }
});
updateButtonState();
