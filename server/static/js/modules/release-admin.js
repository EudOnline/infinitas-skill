import { apiPost, copyToClipboard } from './api.js';
import { uiText } from './config.js';

function setButtonBusy(button, busy) {
  if (!button) return;
  if (!button.dataset.label) {
    button.dataset.label = button.textContent || '';
  }
  button.disabled = busy;
  button.textContent = busy
    ? uiText('action_working', 'Working...')
    : button.dataset.label;
}

function buildResultRow(label, value, copyValue = '') {
  const row = document.createElement('div');
  row.className = 'flex flex-wrap items-center justify-between gap-2 py-2 border-b border-kawaii-line/50 last:border-0';

  const meta = document.createElement('div');
  const strong = document.createElement('strong');
  strong.className = 'block text-sm text-kawaii-ink';
  strong.textContent = label;
  const valueEl = document.createElement('code');
  valueEl.className = 'text-sm text-kawaii-ink-soft break-all';
  valueEl.textContent = value || '-';
  meta.appendChild(strong);
  meta.appendChild(valueEl);
  row.appendChild(meta);

  if (copyValue) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'kawaii-button kawaii-button--ghost text-sm';
    button.textContent = uiText('action_copy', 'Copy');
    button.addEventListener('click', () => copyToClipboard(copyValue));
    row.appendChild(button);
  }

  return row;
}

function renderResult(container, title, rows) {
  if (!container) return;
  container.hidden = false;
  const fragment = document.createDocumentFragment();

  const heading = document.createElement('div');
  heading.className = 'font-bold text-kawaii-ink mb-2';
  heading.textContent = title;
  fragment.appendChild(heading);

  rows.forEach((row) => {
    fragment.appendChild(buildResultRow(row.label, row.value, row.copyValue));
  });

  container.replaceChildren(fragment);
}

function showSuccess(message) {
  window.toast?.success?.(message);
}

function showError(message) {
  window.toast?.error?.(message);
}

function initIssueTokenForm() {
  const form = document.getElementById('issue-token-form');
  const result = document.getElementById('issue-token-result');
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector('button[type="submit"]');
    setButtonBusy(submitButton, true);

    try {
      const releaseId = form.dataset.releaseId;
      const payload = {
        token_type: form.elements.token_type.value,
        label: String(form.elements.label.value || '').trim() || null,
      };
      const data = await apiPost(
        `/api/library/releases/${encodeURIComponent(releaseId)}/tokens`,
        payload,
      );
      renderResult(result, uiText('token_created', 'Token created'), [
        {
          label: uiText('table_col_type', 'Type'),
          value: data.token_type,
        },
        {
          label: uiText('table_col_token', 'Token'),
          value: data.token,
          copyValue: data.token,
        },
        {
          label: uiText('label_scopes', 'Scopes'),
          value: Array.isArray(data.scopes) ? data.scopes.join(', ') : '-',
        },
      ]);
      form.reset();
      showSuccess(uiText('token_created', 'Token created'));
    } catch (error) {
      showError(error.message || uiText('token_create_error', 'Failed to create token'));
    } finally {
      setButtonBusy(submitButton, false);
    }
  });
}

function initCreateShareForm() {
  const form = document.getElementById('create-share-form');
  const result = document.getElementById('create-share-result');
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector('button[type="submit"]');
    setButtonBusy(submitButton, true);

    try {
      const releaseId = form.dataset.releaseId;
      const payload = {
        label: String(form.elements.label.value || '').trim() || null,
        temporary_password: String(form.elements.temporary_password.value || '').trim() || null,
        expires_in_days: Number(form.elements.expires_in_days.value || 7),
        usage_limit: Number(form.elements.usage_limit.value || 5),
      };
      const data = await apiPost(
        `/api/library/releases/${encodeURIComponent(releaseId)}/share-links`,
        payload,
      );
      renderResult(result, uiText('share_created', 'Share link created'), [
        {
          label: uiText('table_col_release', 'Release URL'),
          value: data.install_url,
          copyValue: data.install_url,
        },
        {
          label: uiText('table_col_password', 'Password'),
          value: data.temporary_password,
          copyValue: data.temporary_password,
        },
        {
          label: uiText('table_col_expiry', 'Expiry'),
          value: data.expires_at,
        },
      ]);
      form.reset();
      form.elements.expires_in_days.value = '7';
      form.elements.usage_limit.value = '5';
      showSuccess(uiText('share_created', 'Share link created'));
    } catch (error) {
      showError(error.message || uiText('share_create_error', 'Failed to create share link'));
    } finally {
      setButtonBusy(submitButton, false);
    }
  });
}

function initReleaseAdminPage() {
  initIssueTokenForm();
  initCreateShareForm();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initReleaseAdminPage);
} else {
  initReleaseAdminPage();
}

export { initReleaseAdminPage };
