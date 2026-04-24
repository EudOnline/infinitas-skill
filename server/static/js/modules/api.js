/**
 * API utility functions and clipboard helpers
 */
import { uiText } from './config.js';

// ── Toast reference (set by the application bootstrap) ──────────────
let toastRef = null;
export function setApiToastRef(ref) { toastRef = ref; }

// ── Clipboard ───────────────────────────────────────────────────────

async function copyToClipboard(text) {
  if (!text) {
    if (toastRef) toastRef.error(uiText('copy_error', '复制失败'));
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    if (toastRef) toastRef.success(uiText('copy_success', '已复制'));
  } catch (_err) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    try {
      textarea.select();
      document.execCommand('copy');
      if (toastRef) toastRef.success(uiText('copy_success', '已复制'));
    } catch (_e) {
      if (toastRef) toastRef.error(uiText('copy_error', '复制失败'));
    } finally {
      document.body.removeChild(textarea);
    }
  }
}

function bindCopyTriggers(root = document) {
  if (!root || typeof root.querySelectorAll !== 'function') {
    return;
  }

  root.querySelectorAll('[data-copy]').forEach((trigger) => {
    if (trigger.dataset.copyBound === 'true') {
      return;
    }
    trigger.dataset.copyBound = 'true';
    trigger.addEventListener('click', () => copyToClipboard(trigger.dataset.copy || ''));
  });
}

// ── HTTP helpers ────────────────────────────────────────────────────

async function parseApiError(response) {
  let message = '';
  try {
    const data = await response.json();
    message = data.detail || data.message || JSON.stringify(data);
  } catch (_e) {
    message = response.statusText || `HTTP ${response.status}`;
  }
  const err = new Error(message);
  err.status = response.status;
  return err;
}

async function apiGet(url, signal) {
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'same-origin',
    signal,
  });
  if (!response.ok) {
    const err = await parseApiError(response);
    throw err;
  }
  return response.json();
}

async function apiPost(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await parseApiError(response);
    throw err;
  }
  return response.json();
}

async function apiPatch(url, body) {
  const response = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await parseApiError(response);
    throw err;
  }
  return response.json();
}

// ── Pending toasts (sessionStorage) ─────────────────────────────────

function drainPendingToasts() {
  try {
    const keys = Object.keys(sessionStorage).filter(k => k.startsWith('lifecycle_toast_'));
    keys.forEach((key) => {
      const raw = sessionStorage.getItem(key);
      sessionStorage.removeItem(key);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data && data.type && data.message && toastRef) {
        toastRef.show(data.message, data.type, 4000);
      }
    });
  } catch (_e) {}
}

// ── Exports ─────────────────────────────────────────────────────────

export {
  copyToClipboard,
  bindCopyTriggers,
  apiGet,
  apiPost,
  apiPatch,
  drainPendingToasts,
};
