/**
 * Core configuration and data parsing
 */

function parseJsonData(id) {
  try {
    const el = document.getElementById(id);
    return el && el.dataset.json ? JSON.parse(el.dataset.json) : {};
  } catch (_) {
    return {};
  }
}

export const APP_UI = parseJsonData('app-ui-data');
export const APP_SESSION = parseJsonData('app-session-data');

const APP_AUTH_CONFIG = parseJsonData('app-auth-config-data');
const HOME_AUTH_SESSION_CONFIG = parseJsonData('home-auth-session-data');

export const AUTH_SESSION_CONFIG = {
  ...APP_AUTH_CONFIG,
  ...HOME_AUTH_SESSION_CONFIG,
};

export function currentPageLanguage() {
  const lang = (document.documentElement.lang || '').toLowerCase();
  return lang.startsWith('en') ? 'en' : 'zh';
}

export function currentSearchScope() {
  if (document.body?.classList.contains('page-console')) {
    return 'me';
  }
  return 'public';
}

export function uiText(key, fallback) {
  const value = APP_UI[key];
  return typeof value === 'string' && value ? value : fallback;
}

export function isSafeUrl(url) {
  return typeof url === 'string' && /^https?:\/\//.test(url);
}

export function sanitizeClassName(text) {
  return String(text || '').trim().replace(/\s+/g, '-').replace(/[^a-zA-Z0-9_-]/g, '');
}

export function uiTemplate(key, fallback, replacements = {}) {
  let template = uiText(key, fallback);
  Object.entries(replacements).forEach(([name, value]) => {
    template = template.replaceAll(`{${name}}`, String(value));
  });
  return template;
}

/**
 * Log errors only in development (localhost) to avoid leaking info in production.
 */
export function logError(...args) {
  const hostname = window.location.hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    console.error(...args);
  }
}

/**
 * Read the CSRF token — prefer <meta> tag, fall back to cookie.
 */
export function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  if (!match) return '';
  try {
    return decodeURIComponent(match[1]);
  } catch (_e) {
    return match[1];
  }
}
