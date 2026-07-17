/** Console-page authentication session manager. */

import {
  remainingDays,
  clearLocalSession,
  hasAuthCookieHint,
  setAuthCookieHint,
  initialSessionUser,
  requestSessionCleanup,
} from './auth-shared.js';
import { AUTH_SESSION_CONFIG, logError, uiTemplate, uiText } from './config.js';
import { createAuthModalController } from './auth-modal.js';

let toastRef = null;

export function setToastRef(toastInstance) {
  toastRef = toastInstance;
}

class ConsoleAuthSession {
  constructor(root) {
    this.root = root;
    this.currentUser = initialSessionUser();
    this.panelOpen = false;
    this.controller = createAuthModalController({
      prefix: 'console-',
      modalTitle: uiText('console_auth_modal_title', 'Identity check'),
      onLoginSuccess: (data) => this.applyLogin(data),
    });
  }

  element(id) {
    return document.getElementById(id);
  }

  roleLabel(role) {
    const normalized = (role || '').toLowerCase();
    if (normalized === 'maintainer') return uiText('role_maintainer', 'Maintainer');
    if (normalized === 'contributor') return uiText('role_contributor', 'Contributor');
    return normalized || uiText('console_session_ready', 'Session ready');
  }

  sessionMeta() {
    const role = this.currentUser?.role
      ? uiTemplate('console_session_role', 'Role: {role}', {
        role: this.roleLabel(this.currentUser.role),
      })
      : uiText('console_session_ready', 'Session ready');
    const days = remainingDays();
    const expiry = days > 0
      ? uiTemplate('auth_expiry_days', 'Expires in {days} days', { days })
      : uiText('auth_session_active', 'Session active');
    return `${role} · ${expiry}`;
  }

  closePanel() {
    const panel = this.element('console-session-panel');
    const trigger = this.element('console-session-trigger');
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    this.panelOpen = false;
    trigger?.setAttribute('aria-expanded', 'false');
  }

  renderSessionState() {
    const authenticated = Boolean(this.currentUser);
    const icon = this.element('console-session-icon');
    const label = this.element('console-session-label');
    const trigger = this.element('console-session-trigger');
    const anonSection = this.element('console-session-anon');
    const loggedSection = this.element('console-session-logged');
    if (icon) (icon.querySelector('[aria-hidden]') || icon).textContent = authenticated ? '👤' : '🔒';
    if (label) {
      label.textContent = authenticated
        ? this.currentUser.username
        : uiText('console_session_guest', 'Sign in');
    }
    trigger?.setAttribute(
      'aria-label',
      authenticated
        ? uiText('user_menu_logged_label', 'Account menu')
        : uiText('user_menu_anon_label', 'Sign in'),
    );
    if (anonSection) anonSection.hidden = authenticated;
    if (loggedSection) loggedSection.hidden = !authenticated;
    if (!authenticated) return;
    const username = this.element('console-session-username');
    const meta = this.element('console-session-meta');
    const avatar = this.element('console-session-avatar');
    if (username) username.textContent = this.currentUser.username;
    if (meta) meta.textContent = this.sessionMeta();
    if (avatar) avatar.textContent = (this.currentUser.username || 'U').charAt(0).toUpperCase();
  }

  togglePanel() {
    const panel = this.element('console-session-panel');
    const trigger = this.element('console-session-trigger');
    if (!panel || !trigger) return;
    if (!panel.hidden) {
      this.closePanel();
      return;
    }
    panel.hidden = false;
    this.panelOpen = true;
    trigger.setAttribute('aria-expanded', 'true');
  }

  async refreshCurrentUser() {
    const response = await fetch('/api/v1/auth/me', { credentials: 'same-origin' });
    if (!response.ok) throw new Error('auth probe failed');
    const payload = await response.json();
    this.currentUser = payload.authenticated
      ? { username: payload.username, role: payload.role || null }
      : null;
    setAuthCookieHint(Boolean(this.currentUser));
    this.renderSessionState();
    return this.currentUser;
  }

  async initAuthState() {
    if (this.currentUser) {
      setAuthCookieHint(true);
      this.renderSessionState();
      return;
    }
    if (!hasAuthCookieHint() && remainingDays() <= 0) {
      this.clearSessionState();
      return;
    }
    try {
      if (await this.refreshCurrentUser()) return;
    } catch (error) {
      logError('Console auth validation failed:', error);
    }
    await requestSessionCleanup('Console logout request failed:');
    this.clearSessionState();
  }

  clearSessionState() {
    clearLocalSession();
    this.currentUser = null;
    this.renderSessionState();
  }

  async handleLogout() {
    clearLocalSession();
    await requestSessionCleanup('Console logout request failed:');
    this.currentUser = null;
    this.renderSessionState();
    this.closePanel();
    window.location.href = AUTH_SESSION_CONFIG.homeHref || '/';
  }

  applyLogin(data) {
    this.currentUser = { username: data.username, role: data.role || null };
    this.renderSessionState();
    toastRef?.success(uiText('auth_session_active', 'Session active'));
  }

  handleDocumentClick(event) {
    const trigger = this.element('console-session-trigger');
    const panel = this.element('console-session-panel');
    const clickedOutside = trigger && panel
      && !trigger.contains(event.target)
      && !panel.contains(event.target);
    if (this.panelOpen && clickedOutside) this.closePanel();
  }

  handleAuthChanged(event) {
    this.currentUser = event.detail.authenticated
      ? { username: event.detail.username, role: event.detail.role || null }
      : null;
    this.renderSessionState();
  }

  bindEvents() {
    this.element('console-session-trigger')?.addEventListener('click', () => this.togglePanel());
    this.element('console-logout-btn')?.addEventListener('click', () => this.handleLogout());
    document.addEventListener('click', (event) => this.handleDocumentClick(event));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && this.panelOpen) this.closePanel();
    });
    document.addEventListener('infinitas:auth-changed', (event) => this.handleAuthChanged(event));
  }

  async init() {
    this.renderSessionState();
    this.bindEvents();
    await this.initAuthState();
  }
}

export function initConsoleAuthSession() {
  const root = document.getElementById('console-session-root');
  if (!root) return;
  new ConsoleAuthSession(root).init();
}
