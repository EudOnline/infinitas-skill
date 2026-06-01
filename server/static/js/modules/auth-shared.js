/**
 * Shared authentication utilities and constants.
 *
 * Re-exports thin wrappers around config.js helpers so that the auth
 * sub-modules (auth-modal, auth-home, auth-console) share a single source
 * of truth for session storage keys, credential validation, and cookie-hint state.
 */

import {
  APP_SESSION,
  AUTH_SESSION_CONFIG,
  uiText,
  logError,
  getCsrfToken,
  uiTemplate,
  currentPageLanguage,
} from './config.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EXPIRY_KEY = 'infinitas_auth_expiry';
const DAYS_30 = 30 * 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Convenience re-exports from config (kept as wrapper functions for
// backward compatibility with the call-sites in auth-session.js).
// ---------------------------------------------------------------------------

export { currentPageLanguage, uiText, uiTemplate, getCsrfToken };

// ---------------------------------------------------------------------------
// Session state helpers
// ---------------------------------------------------------------------------

/**
 * Write a fresh 30-day expiry marker into localStorage.
 */
export function markLocalSessionActive() {
  try {
    window.localStorage.setItem(EXPIRY_KEY, String(Date.now() + DAYS_30));
  } catch (_error) {
    // Ignore storage failures so cookie-backed auth can still work.
  }
}

/**
 * Remove the local token and expiry markers from localStorage.
 */
export function clearLocalSession() {
  try {
    window.localStorage.removeItem(EXPIRY_KEY);
  } catch (_error) {
    // Ignore storage cleanup failures.
  }
}

/**
 * Return the number of full days remaining before the local expiry marker
 * expires.  Returns 0 when the marker is missing or already past.
 */
export function remainingDays() {
  try {
    const raw = window.localStorage.getItem(EXPIRY_KEY);
    if (!raw) {
      return 0;
    }
    return Math.max(0, Math.ceil((Number(raw) - Date.now()) / 86400000));
  } catch (_error) {
    return 0;
  }
}

// ---------------------------------------------------------------------------
// Cookie-hint helpers (in-memory flag mirrored on APP_SESSION)
// ---------------------------------------------------------------------------

/**
 * Check whether a server-side auth cookie is expected to be present.
 */
export function hasAuthCookieHint() {
  return APP_SESSION.has_auth_cookie_hint === true || APP_SESSION.hasAuthCookieHint === true;
}

/**
 * Record (or clear) the in-memory hint that a server-side auth cookie exists.
 */
export function setAuthCookieHint(present) {
  APP_SESSION.has_auth_cookie_hint = present;
  APP_SESSION.hasAuthCookieHint = present;
}

// ---------------------------------------------------------------------------
// Initial user extraction
// ---------------------------------------------------------------------------

/**
 * Try to read the current user from the server-rendered session bootstrap.
 */
export function initialSessionUser() {
  try {
    const el = document.getElementById('session-bootstrap-data');
    if (!el || !el.dataset.json) return null;
    const parsed = JSON.parse(el.dataset.json);
    return parsed.current_user || null;
  } catch (_error) {
    return null;
  }
}

/**
 * Send a POST to /api/auth/logout and clear local state.
 */
export async function requestSessionCleanup() {
  try {
    const csrfToken = getCsrfToken();
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
    });
  } catch (_error) {
    // Best-effort logout
  }
  clearLocalSession();
  setAuthCookieHint(false);
}

// ---------------------------------------------------------------------------
// Credential validation
// ---------------------------------------------------------------------------

export function validateCredentials(username, password) {
  if (!username || !username.trim()) {
    return uiText('auth_enter_username', 'Please enter username');
  }
  if (username.length < 1) {
    return uiText('auth_username_min', 'Username must be at least 1 character');
  }
  if (username.length > 100) {
    return uiText('auth_username_max', 'Username must not exceed 100 characters');
  }
  if (!password || !password.trim()) {
    return uiText('auth_enter_password', 'Please enter password');
  }
  if (password.length < 1) {
    return uiText('auth_password_min', 'Password must be at least 1 character');
  }
  if (password.length > 128) {
    return uiText('auth_password_max', 'Password must not exceed 128 characters');
  }
  return null;
}
