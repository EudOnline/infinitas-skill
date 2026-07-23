import { apiGet, apiPost, copyToClipboard } from './api.js';
import { uiText } from './config.js';
import { getSharedToast } from './toast.js';

const form = document.getElementById('namespace-token-form');
const result = document.getElementById('namespace-token-result');
const list = document.getElementById('namespace-token-list');

function setBusy(button, busy) {
  if (!button) return;
  if (!button.dataset.label) button.dataset.label = button.textContent || '';
  button.disabled = busy;
  button.textContent = busy ? uiText('action_working', 'Working...') : button.dataset.label;
}

function button(label, className = 'kawaii-button kawaii-button--ghost text-sm') {
  const element = document.createElement('button');
  element.type = 'button';
  element.className = className;
  element.textContent = label;
  return element;
}

function renderCreated(data) {
  const heading = document.createElement('strong');
  heading.className = 'block text-sm text-kawaii-ink mb-2';
  heading.textContent = uiText('token_created', 'Token created');
  const row = document.createElement('div');
  row.className = 'flex flex-col sm:flex-row sm:items-center gap-2';
  const code = document.createElement('code');
  code.className = 'text-sm text-kawaii-ink break-all flex-1';
  code.textContent = data.raw_token;
  const copy = button(uiText('action_copy', 'Copy'));
  copy.addEventListener('click', () => copyToClipboard(data.raw_token));
  row.append(code, copy);
  result.replaceChildren(heading, row);
  result.hidden = false;
}

function tokenTable(items) {
  const table = document.createElement('table');
  table.className = 'w-full text-sm';
  const head = document.createElement('thead');
  const headerRow = document.createElement('tr');
  [
    uiText('label_token_name', 'Name'),
    uiText('label_token_type', 'Type'),
    uiText('label_state', 'State'),
    uiText('label_scopes', 'Scopes'),
    uiText('col_actions', 'Actions'),
  ].forEach((label) => {
    const cell = document.createElement('th');
    cell.scope = 'col';
    cell.textContent = label;
    headerRow.appendChild(cell);
  });
  head.appendChild(headerRow);
  const body = document.createElement('tbody');
  items.forEach((item) => {
    const row = document.createElement('tr');
    [item.name, item.type, item.state, (item.scopes || []).join(', ')].forEach((value) => {
      const cell = document.createElement('td');
      cell.textContent = value || '-';
      row.appendChild(cell);
    });
    const actions = document.createElement('td');
    if (item.state === 'active') {
      const revoke = button(uiText('action_revoke', 'Revoke'));
      revoke.addEventListener('click', async () => {
        setBusy(revoke, true);
        try {
          await apiPost(`/api/v1/namespace-tokens/${encodeURIComponent(item.id)}/revoke`);
          getSharedToast()?.success(uiText('token_revoked', 'Token revoked'));
          await loadTokens();
        } catch (error) {
          getSharedToast()?.error(error.message || uiText('token_revoke_error', 'Revoke failed'));
        } finally {
          setBusy(revoke, false);
        }
      });
      actions.appendChild(revoke);
    }
    row.appendChild(actions);
    body.appendChild(row);
  });
  table.append(head, body);
  return table;
}

async function loadTokens() {
  if (!list) return;
  try {
    const data = await apiGet('/api/v1/namespace-tokens');
    if (!data.items.length) {
      const empty = document.createElement('p');
      empty.className = 'text-sm text-kawaii-ink-muted py-4 text-center';
      empty.textContent = uiText('empty_tokens', 'No tokens');
      list.replaceChildren(empty);
      return;
    }
    list.replaceChildren(tokenTable(data.items));
  } catch (error) {
    getSharedToast()?.error(error.message || uiText('token_create_error', 'Token load failed'));
  }
}

function syncPublisherFields() {
  const publisher = form?.elements.token_type.value === 'publisher';
  document.querySelectorAll('[data-publisher-field]').forEach((field) => {
    field.hidden = !publisher;
  });
}

form?.elements.token_type.addEventListener('change', syncPublisherFields);
form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = form.querySelector('button[type="submit"]');
  setBusy(submit, true);
  const publisher = form.elements.token_type.value === 'publisher';
  const payload = {
    name: String(form.elements.name.value || '').trim(),
    type: form.elements.token_type.value,
    expires_in_days: Number(form.elements.expires_in_days.value),
    max_daily_publishes: publisher
      ? Number(form.elements.max_daily_publishes.value)
      : null,
  };
  try {
    const data = await apiPost('/api/v1/namespace-tokens', payload);
    renderCreated(data);
    getSharedToast()?.success(uiText('token_created', 'Token created'));
    form.elements.name.value = '';
    await loadTokens();
  } catch (error) {
    getSharedToast()?.error(error.message || uiText('token_create_error', 'Create failed'));
  } finally {
    setBusy(submit, false);
  }
});

syncPublisherFields();
loadTokens();
