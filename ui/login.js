(() => {
  const role = document.body.dataset.role;
  const endpoint = role === 'agent' ? '/agent' : '/review';
  const form = document.querySelector('#login-form');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = document.querySelector('#login-submit');
    const error = document.querySelector('#login-error');
    const password = document.querySelector('#password');
    button.disabled = true;
    error.textContent = '';
    try {
      const response = await fetch(endpoint + '/login', {
        method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: document.querySelector('#username').value.trim(), password: password.value}),
        signal: AbortSignal.timeout(15000)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Sign-in failed. Please try again.');
      if (result.role !== role) throw new Error('This account does not match this workspace.');
      password.value = '';
      window.location.assign(endpoint + (new URLSearchParams(location.search).has('demo') ? '?demo=1' : ''));
    } catch (failure) {
      password.value = '';
      error.textContent = failure.name === 'TimeoutError' ? 'The server took too long. Please try again.' : failure.message;
      button.disabled = false;
    }
  });
})();
