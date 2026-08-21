const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

const bindCopyPrompt = () => {
  const button = document.getElementById('copy-agent-prompt');
  if (!button || button.dataset.bound === 'true') return;
  button.dataset.bound = 'true';
  button.addEventListener('click', async () => {
    const prompt = document.getElementById('agent-prompt');
    const status = document.getElementById('copy-agent-prompt-status');
    if (!(prompt instanceof HTMLTextAreaElement) || !status) return;
    try {
      await navigator.clipboard.writeText(prompt.value);
      status.textContent = '已复制。';
    } catch {
      prompt.focus();
      prompt.select();
      status.textContent = '无法自动复制，请手动复制已选中的内容。';
    }
  });
};

const renderHtmlResponse = (html) => {
  const parsed = new DOMParser().parseFromString(html, 'text/html');
  document.title = parsed.title;
  document.body.replaceWith(document.importNode(parsed.body, true));
  bindAgentPage();
};

const bindAgentForms = () => {
  document.querySelectorAll('form[method="post"]').forEach((form) => {
    if (form.dataset.bound === 'true') return;
    form.dataset.bound = 'true';
    form.addEventListener('submit', async (event) => {
      const token = csrf();
      if (!token) return;
      event.preventDefault();
      const response = await fetch(form.action, {
        method: 'POST',
        body: new URLSearchParams(new FormData(form)),
        headers: { 'X-CSRF-Token': token },
        credentials: 'same-origin',
        redirect: 'follow',
      });
      if (response.redirected) {
        window.location.assign(response.url);
        return;
      }
      renderHtmlResponse(await response.text());
    });
  });
};

function bindAgentPage() {
  bindAgentForms();
  bindCopyPrompt();
}

bindAgentPage();
