import { apiPost, copyToClipboard } from './api.js';
import { uiText } from './config.js';
import { getSharedToast } from './toast.js';
import {
  initDelegatedActions,
  initShareDetail,
  setLifecycleToastRef,
} from './lifecycle.js';

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
  getSharedToast()?.success(message);
}

function showError(message) {
  getSharedToast()?.error(message);
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
      const objectId = form.dataset.objectId;
      const releaseId = form.dataset.releaseId;
      const payload = {
        name: String(form.elements.label.value || '').trim() || 'release token',
        type: form.elements.token_type.value,
        scope_type: 'release',
        scope_id: Number(releaseId),
      };
      const data = await apiPost(
        `/api/v1/object-tokens/objects/${encodeURIComponent(objectId)}/tokens`,
        payload,
      );
      renderResult(result, uiText('token_created', 'Token created'), [
        {
          label: uiText('table_col_type', 'Type'),
          value: data.token.type,
        },
        {
          label: uiText('table_col_token', 'Token'),
          value: data.raw_token,
          copyValue: data.raw_token,
        },
        {
          label: uiText('label_scopes', 'Scopes'),
          value: Array.isArray(data.token.scopes) ? data.token.scopes.join(', ') : '-',
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
      const suppliedPassword = String(form.elements.temporary_password.value || '').trim();
      const payload = {
        name: String(form.elements.label.value || '').trim() || 'share link',
        password: suppliedPassword || null,
        expires_in_days: Number(form.elements.expires_in_days.value || 7),
        max_uses: Number(form.elements.usage_limit.value || 5),
      };
      const data = await apiPost(
        `/api/v1/share-links/releases/${encodeURIComponent(releaseId)}/share-links`,
        payload,
      );
      const installCommand = `infinitas install from-share '${data.resolve_url}' '<target-dir>'`;
      renderResult(result, uiText('share_created', 'Share link created'), [
        {
          label: uiText('share_resolve_url', 'Resolve URL'),
          value: data.resolve_url,
          copyValue: data.resolve_url,
        },
        {
          label: uiText('share_agent_install_command', 'Agent install command'),
          value: installCommand,
          copyValue: installCommand,
        },
        {
          label: suppliedPassword
            ? uiText('table_col_password', 'Password')
            : uiText('share_resolve_secret', 'Resolve secret'),
          value: suppliedPassword || data.resolve_secret,
          copyValue: suppliedPassword || data.resolve_secret,
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
  setLifecycleToastRef(getSharedToast());
  initDelegatedActions();
  initShareDetail();
  initIssueTokenForm();
  initCreateShareForm();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initReleaseAdminPage);
} else {
  initReleaseAdminPage();
}

export { initReleaseAdminPage };
