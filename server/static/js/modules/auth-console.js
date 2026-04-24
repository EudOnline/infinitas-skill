/**
 * Console-page authentication session manager.
 *
 * Handles the console session trigger, session panel, logout, and the
 * console-prefixed login modal lifecycle.
 */

import {
  uiText,
  uiTemplate,
  remainingDays,
  clearLocalSession,
  hasAuthCookieHint,
  setAuthCookieHint,
  initialSessionUser,
  requestSessionCleanup,
} from './auth-shared.js';

import { AUTH_SESSION_CONFIG } from './config.js';
import { createAuthModalController } from './auth-modal.js';

// ---------------------------------------------------------------------------
// Toast reference (set externally via the toastRef setter pattern)
// ---------------------------------------------------------------------------

let _toast = null;

/**
 * Accept a toast manager instance from the outside so this module can call
 * `_toast.success(...)` etc. without importing the toast module itself.
 */
export function setToastRef(toastInstance) {
  _toast = toastInstance;
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function initConsoleAuthSession() {
  const root = document.getElementById('console-session-root');
  if (!root) {
    return;
  }

  let currentUser = initialSessionUser();
  let panelOpen = false;

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  function roleLabel(role) {
    const normalized = (role || '').toLowerCase();
    if (normalized === 'maintainer') {
      return uiText('role_maintainer', 'Maintainer');
    }
    if (normalized === 'contributor') {
      return uiText('role_contributor', 'Contributor');
    }
    return normalized || uiText('console_session_ready', 'Session ready');
  }

  function sessionMeta() {
    const role = currentUser?.role
      ? uiTemplate('console_session_role', 'Role: {role}', { role: roleLabel(currentUser.role) })
      : uiText('console_session_ready', 'Session ready');
    const days = remainingDays();
    if (days > 0) {
      return `${role} · ${uiTemplate('auth_expiry_days', 'Expires in {days} days', { days })}`;
    }
    return `${role} · ${uiText('auth_session_active', 'Session active')}`;
  }

  // -----------------------------------------------------------------------
  // Panel management
  // -----------------------------------------------------------------------

  function closePanel() {
    const panel = document.getElementById('console-session-panel');
    const trigger = document.getElementById('console-session-trigger');
    if (!panel || panel.hidden) {
      return;
    }
    panel.hidden = true;
    panelOpen = false;
    if (trigger) {
      trigger.setAttribute('aria-expanded', 'false');
    }
  }

  function renderSessionState() {
    const trigger = document.getElementById('console-session-trigger');
    const icon = document.getElementById('console-session-icon');
    const label = document.getElementById('console-session-label');
    const anonSection = document.getElementById('console-session-anon');
    const loggedSection = document.getElementById('console-session-logged');
    const username = document.getElementById('console-session-username');
    const meta = document.getElementById('console-session-meta');
    const avatar = document.getElementById('console-session-avatar');
    const authenticated = !!currentUser;
    if (icon) {
      const inner = icon.querySelector('[aria-hidden]') || icon;
      inner.textContent = authenticated ? '👤' : '🔒';
    }
    if (label) {
      label.textContent = authenticated ? currentUser.username : uiText('console_session_guest', 'Sign in');
    }
    if (trigger) {
      trigger.setAttribute(
        'aria-label',
        authenticated
          ? uiText('user_menu_logged_label', 'Account menu')
          : uiText('user_menu_anon_label', 'Sign in')
      );
    }
    if (anonSection) {
      anonSection.hidden = authenticated;
    }
    if (loggedSection) {
      loggedSection.hidden = !authenticated;
    }
    if (authenticated) {
      if (username) {
        username.textContent = currentUser.username;
      }
      if (meta) {
        meta.textContent = sessionMeta();
      }
      if (avatar) {
        avatar.textContent = (currentUser.username || 'U').charAt(0).toUpperCase();
      }
    }
  }

  function togglePanel() {
    const panel = document.getElementById('console-session-panel');
    const trigger = document.getElementById('console-session-trigger');
    if (!panel || !trigger) {
      return;
    }
    if (panel.hidden) {
      panel.hidden = false;
      panelOpen = true;
      trigger.setAttribute('aria-expanded', 'true');
      return;
    }
    closePanel();
  }

  // -----------------------------------------------------------------------
  // Auth state management
  // -----------------------------------------------------------------------

  async function refreshCurrentUser() {
    const response = await fetch('/api/auth/me', { credentials: 'same-origin' });
    if (!response.ok) {
      throw new Error('auth probe failed');
    }
    const payload = await response.json();
    currentUser = payload.authenticated ? { username: payload.username, role: payload.role || null } : null;
    setAuthCookieHint(!!currentUser);
    renderSessionState();
    return currentUser;
  }

  async function initAuthState() {
    const shouldProbeAuth = hasAuthCookieHint() || remainingDays() > 0;
    if (currentUser) {
      setAuthCookieHint(true);
      renderSessionState();
      return;
    }
    if (!shouldProbeAuth) {
      clearLocalSession();
      currentUser = null;
      renderSessionState();
      return;
    }
    try {
      const user = await refreshCurrentUser();
      if (user) {
        return;
      }
    } catch (error) {
      console.error('Console auth validation failed:', error);
    }
    await requestSessionCleanup('Console logout request failed:');
    clearLocalSession();
    currentUser = null;
    renderSessionState();
  }

  async function handleLogout() {
    clearLocalSession();
    await requestSessionCleanup('Console logout request failed:');
    currentUser = null;
    renderSessionState();
    closePanel();
    window.location.href = AUTH_SESSION_CONFIG.homeHref || '/';
  }

  // -----------------------------------------------------------------------
  // Event handlers
  // -----------------------------------------------------------------------

  function handleDocumentClick(event) {
    const trigger = document.getElementById('console-session-trigger');
    const panel = document.getElementById('console-session-panel');
    if (panelOpen && trigger && panel && !trigger.contains(event.target) && !panel.contains(event.target)) {
      closePanel();
    }
  }

  function handleKeyDown(event) {
    if (event.key !== 'Escape') {
      return;
    }
    if (panelOpen) {
      closePanel();
    }
  }

  function bindEvents() {
    document.getElementById('console-session-trigger')?.addEventListener('click', togglePanel);
    document.getElementById('console-logout-btn')?.addEventListener('click', handleLogout);
    document.addEventListener('click', handleDocumentClick);
    document.addEventListener('keydown', handleKeyDown);
  }

  // -----------------------------------------------------------------------
  // Modal controller
  // -----------------------------------------------------------------------

  const controller = createAuthModalController({
    prefix: 'console-',
    modalTitle: uiText('console_auth_modal_title', 'Identity check'),
    onLoginSuccess: (data) => {
      currentUser = { username: data.username, role: data.role || null };
      renderSessionState();
      if (_toast) {
        _toast.success(uiText('auth_session_active', 'Session active'));
      }
    },
  });

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------

  async function init() {
    renderSessionState();
    bindEvents();
    await initAuthState();
    document.addEventListener('infinitas:auth-changed', (e) => {
      if (e.detail.authenticated) {
        currentUser = { username: e.detail.username, role: e.detail.role || null };
      } else {
        currentUser = null;
      }
      renderSessionState();
    });
  }

  window.openConsoleAuthModal = controller.openModal;
  init();
}
