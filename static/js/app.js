const typingTagline = document.getElementById('typing-tagline');
const fullText = 'Predict before you go broke.';
let index = 0;
function typeLoop() {
  if (!typingTagline) return;
  typingTagline.textContent = fullText.slice(0, index);
  index = (index + 1) % (fullText.length + 1);
  if (index === 0) {
    setTimeout(typeLoop, 1000);
    return;
  }
  setTimeout(typeLoop, 75);
}
typeLoop();

document.querySelectorAll('.auth-tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.auth-tab').forEach((item) => item.classList.remove('active'));
    tab.classList.add('active');
    const isSignup = tab.dataset.tab === 'signup';
    document.getElementById('signup-name').style.display = isSignup ? 'block' : 'none';
    document.getElementById('submit-btn').textContent = isSignup ? 'Create Account' : 'Login';
  });
});

const passwordField = document.getElementById('password-field');
const toggle = document.getElementById('password-toggle');
if (toggle && passwordField) {
  toggle.addEventListener('click', () => {
    const isPassword = passwordField.type === 'password';
    passwordField.type = isPassword ? 'text' : 'password';
    toggle.textContent = isPassword ? 'Hide' : 'Show';
  });
}

document.getElementById('auth-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const activeTab = document.querySelector('.auth-tab.active').dataset.tab;
  const email = event.target.querySelector('input[type="email"]').value;
  const password = document.getElementById('password-field').value;
  const errorEl = document.getElementById('auth-error');
  const btn = document.getElementById('submit-btn');

  errorEl.style.display = 'none';
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = 'Processing...';

  try {
    if (activeTab === 'signup') {
      const name = document.getElementById('name-field').value;
      const formData = new FormData();
      formData.append('email', email);
      formData.append('password', password);
      formData.append('full_name', name);

      const res = await fetch('/api/signup', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.status === 'success' || data.status === 'partial_success') {
        window.location.href = '/upload.html';
      } else {
        errorEl.textContent = data.message || 'Signup failed';
        errorEl.style.display = 'block';
      }
    } else {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (data.status === 'success') {
        window.location.href = '/dashboard.html';
      } else {
        errorEl.textContent = data.message || 'Login failed';
        errorEl.style.display = 'block';
      }
    }
  } catch (err) {
    console.error(err);
    errorEl.textContent = 'Connection error';
    errorEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});
