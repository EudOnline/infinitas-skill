/** Home and standalone-login authentication session manager. */

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

function parseHomeAuthData() {
  try {
    const element = document.getElementById('home-auth-session-data');
    return element?.dataset.json ? JSON.parse(element.dataset.json) : {};
  } catch (_error) {
    return {};
  }
}

function normalizeProtectedTarget(rawTarget) {
  if (typeof rawTarget !== 'string' || !rawTarget.startsWith('/')) return null;
  return rawTarget.startsWith('//') ? null : rawTarget;
}

class HomeAuthSession {
  constructor(wrapper, loginPanel) {
    const config = parseHomeAuthData();
    this.wrapper = wrapper;
    this.standaloneLoginPage = Boolean(loginPanel && !wrapper);
    this.suppressInitialModal = config.suppressInitialModal === true;
    this.currentUser = initialSessionUser();
    this.isUserPanelOpen = false;
    this.controller = createAuthModalController({
      prefix: this.standaloneLoginPage ? 'login-' : '',
      modalTitle: uiText('auth_modal_title', 'Authentication'),
      onLoginSuccess: (data) => this.applyLogin(data),
    });
  }

  element(id) {
    return document.getElementById(id);
  }

  consumePendingAuthRedirect() {
    const url = new URL(window.location.href);
    if (url.searchParams.get('auth') !== 'required') return null;
    const target = normalizeProtectedTarget(url.searchParams.get('next'));
    url.searchParams.delete('auth');
    url.searchParams.delete('next');
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
    return target;
  }

  openAuthModal(targetHref = null) {
    this.controller.openModal(normalizeProtectedTarget(targetHref));
  }

  updateUserTriggerIcon(authenticated) {
    const icon = this.element('user-trigger-icon');
    const pulse = this.element('user-trigger-pulse');
    const trigger = this.element('user-trigger');
    if (icon) icon.textContent = authenticated ? '👤' : '🔒';
    if (pulse) pulse.hidden = authenticated;
    if (!trigger) return;
    trigger.classList.toggle('is-active', authenticated);
    trigger.setAttribute(
      'aria-label',
      authenticated
        ? uiText('user_menu_logged_label', '已登录用户菜单')
        : uiText('user_menu_anon_label', '登录'),
    );
  }

  sessionMeta() {
    const days = remainingDays();
    return days > 0
      ? uiTemplate('auth_expiry_days', '{days} 天后过期', { days })
      : uiText('auth_session_active', '会话已连接');
  }

  renderUserPanel() {
    const loginSection = this.element('user-panel-login');
    const loggedSection = this.element('user-panel-logged');
    const authenticated = Boolean(this.currentUser);
    if (loginSection) loginSection.hidden = authenticated;
    if (loggedSection) loggedSection.hidden = !authenticated;
    if (!authenticated) return;
    const username = this.element('user-panel-username');
    const expiry = this.element('user-panel-expiry');
    const avatar = this.element('user-avatar');
    if (username) username.textContent = this.currentUser.username;
    if (expiry) expiry.textContent = this.sessionMeta();
    if (avatar) avatar.textContent = this.currentUser.username.charAt(0).toUpperCase();
  }

  renderAuthState() {
    this.updateUserTriggerIcon(Boolean(this.currentUser));
    this.renderUserPanel();
  }

  closeUserPanel() {
    const panel = this.element('user-panel');
    if (!panel || panel.hidden) return;
    this.isUserPanelOpen = false;
    panel.hidden = true;
    panel.classList.remove('user-panel--flip');
    this.element('user-trigger')?.setAttribute('aria-expanded', 'false');
  }

  toggleUserPanel() {
    const panel = this.element('user-panel');
    const trigger = this.element('user-trigger');
    if (!panel || !trigger) return;
    this.isUserPanelOpen = !this.isUserPanelOpen;
    panel.hidden = !this.isUserPanelOpen;
    panel.classList.remove('user-panel--flip');
    trigger.setAttribute('aria-expanded', String(this.isUserPanelOpen));
    if (!this.isUserPanelOpen) return;
    requestAnimationFrame(() => this.flipPanelIntoViewport(panel));
  }

  flipPanelIntoViewport(panel) {
    const rect = panel.getBoundingClientRect();
    const isMobile = window.innerWidth <= 767;
    const shouldFlip = (!isMobile && rect.bottom > window.innerHeight - 12)
      || (isMobile && rect.top < 12);
    panel.classList.toggle('user-panel--flip', shouldFlip);
  }

  async refreshCurrentUser() {
    const response = await fetch('/api/v1/auth/me', { credentials: 'same-origin' });
    if (!response.ok) return null;
    const payload = await response.json();
    if (!payload.authenticated) return null;
    this.currentUser = { username: payload.username, role: payload.role || null };
    setAuthCookieHint(true);
    this.renderAuthState();
    return this.currentUser;
  }

  clearSessionState() {
    clearLocalSession();
    this.currentUser = null;
    this.renderAuthState();
  }

  async initAuthState() {
    if (this.currentUser) {
      setAuthCookieHint(true);
      return;
    }
    if (!hasAuthCookieHint() && remainingDays() <= 0) {
      this.clearSessionState();
      return;
    }
    try {
      if (await this.refreshCurrentUser()) return;
    } catch (error) {
      logError('Auth validation failed:', error);
    }
    await requestSessionCleanup('Failed to clear auth cookie on server:');
    this.clearSessionState();
  }

  async handleLogout() {
    clearLocalSession();
    await requestSessionCleanup('Failed to clear auth cookie on server:');
    this.currentUser = null;
    this.renderAuthState();
    this.closeUserPanel();
    document.dispatchEvent(new CustomEvent(
      'infinitas:auth-changed',
      { detail: { authenticated: false } },
    ));
  }

  applyLogin(data) {
    this.currentUser = { username: data.username, role: data.role || null };
    this.renderAuthState();
    document.dispatchEvent(new CustomEvent(
      'infinitas:auth-changed',
      { detail: { authenticated: true, username: data.username, role: data.role } },
    ));
    if (this.standaloneLoginPage) window.location.href = AUTH_SESSION_CONFIG.homeHref || '/';
  }

  handleProtectedNavigation(event) {
    const link = event.target.closest('[data-auth-required="true"]');
    if (!link || this.currentUser) return;
    event.preventDefault();
    this.openAuthModal(link.dataset.authTarget || link.getAttribute('href') || null);
  }

  bindEvents() {
    this.element('user-trigger')?.addEventListener('click', () => this.toggleUserPanel());
    this.element('logout-btn')?.addEventListener('click', () => this.handleLogout());
    document.querySelectorAll('[data-auth-required="true"]').forEach((link) => {
      link.setAttribute('aria-haspopup', 'dialog');
    });
    document.body.addEventListener('click', (event) => this.handleProtectedNavigation(event));
    document.addEventListener('click', (event) => {
      if (this.wrapper && !this.wrapper.contains(event.target) && this.isUserPanelOpen) {
        this.closeUserPanel();
      }
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && this.isUserPanelOpen) this.closeUserPanel();
    });
  }

  syncInitialModal() {
    const startsVisible = !this.standaloneLoginPage
      && this.controller.dom.modal
      && !this.controller.dom.modal.hidden;
    if (!startsVisible) return;
    if (this.suppressInitialModal && !this.currentUser) this.controller.dom.modal.hidden = true;
    else this.openAuthModal();
  }

  applyPendingRedirect() {
    const target = this.consumePendingAuthRedirect();
    if (!target) return;
    if (this.currentUser) window.location.replace(target);
    else this.openAuthModal(target);
  }

  async init() {
    this.renderAuthState();
    await this.initAuthState();
    if (this.standaloneLoginPage && this.currentUser) {
      window.location.replace(AUTH_SESSION_CONFIG.homeHref || '/');
      return;
    }
    this.bindEvents();
    this.syncInitialModal();
    this.applyPendingRedirect();
  }
}

export function initHomeAuthSession() {
  const wrapper = document.getElementById('user-trigger-wrapper');
  const loginPanel = document.getElementById('login-panel');
  if (!wrapper && !loginPanel) return;
  new HomeAuthSession(wrapper, loginPanel).init();
}
