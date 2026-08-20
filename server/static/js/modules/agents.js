const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

document.querySelectorAll('form[method="post"]').forEach((form) => {
  form.addEventListener('submit', async (event) => {
    const token = csrf();
    if (!token) return;
    event.preventDefault();
    const response = await fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'X-CSRF-Token': token },
      credentials: 'same-origin',
      redirect: 'follow',
    });
    if (!response.ok) {
      document.body.insertAdjacentHTML('afterbegin', `<p role="alert">Request failed (${response.status})</p>`);
      return;
    }
    if (response.redirected) window.location.assign(response.url);
  });
});
