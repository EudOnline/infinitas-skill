/**
 * Shared authentication utilities and constants.
 *
 * Re-exports thin wrappers around config.js helpers so that the auth
 * sub-modules (auth-modal, auth-home, auth-console) share a single source
 * of truth for session storage keys, token validation, and cookie-hint state.
 */

import {
  APP_SESSION,
  AUTH_SESSION_CONFIG,
  infinitasAppShell,
  uiText,
  uiTemplate,
  currentPageLanguage,
} from './config.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const STORAGE_KEY = 'infinitas_auth_token';
export const EXPIRY_KEY = 'infinitas_auth_expiry';
export const DAYS_30 = 30 * 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Convenience re-exports from config (kept as wrapper functions for
// backward compatibility with the call-sites in auth-session.js).
// ---------------------------------------------------------------------------

export { currentPageLanguage, uiText, uiTemplate };

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
    window.localStorage.removeItem(STORAGE_KEY);
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
 * Extract the initial user object from the server-rendered APP_SESSION data.
 * Returns `null` when no valid user information is present.
 */
export function initialSessionUser() {
  const raw = APP_SESSION.current_user || APP_SESSION.currentUser;
  if (!raw || typeof raw.username !== 'string' || !raw.username) {
    return null;
  }
  return {
    username: raw.username,
    role: raw.role || null,
  };
}

// ---------------------------------------------------------------------------
// Network helpers
// ---------------------------------------------------------------------------

/**
 * POST to the server-side logout endpoint to clear the auth cookie, then
 * clear the local cookie hint regardless of outcome.
 */
export async function requestSessionCleanup(logLabel) {
  try {
    const res = await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
    if (!res.ok) {
      console.error(logLabel, res.status, res.statusText);
    }
  } catch (error) {
    console.error(logLabel, error);
  } finally {
    setAuthCookieHint(false);
  }
}

// ---------------------------------------------------------------------------
// Token validation
// ---------------------------------------------------------------------------

/**
 * Validate an auth token string.  Returns an error message (string) when the
 * token is invalid, or `null` when it passes all checks.
 */
export function validateToken(token) {
  if (!token) {
    return uiText('auth_enter_token', 'Please enter token');
  }
  if (token.length < 8) {
    return uiText('auth_token_min', 'Token must be at least 8 characters');
  }
  if (token.length > 128) {
    return uiText('auth_token_max', 'Token must not exceed 128 characters');
  }
  if (/[<>"'&]/.test(token)) {
    return uiText('auth_invalid_characters', 'Token contains invalid characters');
  }
  return null;
}
