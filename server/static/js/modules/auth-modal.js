/** Reusable authentication modal controller. */

import { validateCredentials, markLocalSessionActive, setAuthCookieHint } from './auth-shared.js';
import { currentPageLanguage, getCsrfToken, uiText } from './config.js';

const ID_SUFFIXES = {
  trigger: 'open-auth-modal-btn',
  modal: 'auth-modal',
  backdrop: 'auth-modal-backdrop',
  close: 'auth-modal-close',
  cancel: 'cancel-auth-btn',
  form: 'auth-form',
  usernameInput: 'username-input',
  passwordInput: 'password-input',
  passwordToggle: 'password-toggle',
  error: 'auth-error',
  errorMessage: 'error-message',
  hint: 'auth-hint',
  loginBtn: 'login-btn',
};

class AuthModalController {
  constructor(options = {}) {
    this.prefix = options.prefix || '';
    this.onLoginSuccess = options.onLoginSuccess || null;
    this.isModalOpen = false;
    this.loginInProgress = false;
    this.pendingRedirect = null;
    this.errorTimeout = null;
    this.focusTimer = null;
    this.dom = this.cacheElements();
    this.bindEvents();
  }

  cacheElements() {
    return Object.fromEntries(
      Object.entries(ID_SUFFIXES).map(([key, suffix]) => [
        key,
        document.getElementById(this.prefix + suffix),
      ]),
    );
  }

  showError(message) {
    if (!this.dom.errorMessage || !this.dom.error) return;
    this.dom.errorMessage.textContent = message;
    this.dom.error.hidden = false;
    this.dom.usernameInput?.setAttribute('aria-invalid', 'true');
    this.dom.passwordInput?.setAttribute('aria-invalid', 'true');
    clearTimeout(this.errorTimeout);
    this.errorTimeout = setTimeout(() => {
      if (this.dom.error) this.dom.error.hidden = true;
      this.errorTimeout = null;
    }, 5000);
  }

  hideError() {
    if (!this.dom.error) return;
    this.dom.error.hidden = true;
    this.dom.usernameInput?.removeAttribute('aria-invalid');
    this.dom.passwordInput?.removeAttribute('aria-invalid');
    clearTimeout(this.errorTimeout);
    this.errorTimeout = null;
  }

  togglePasswordVisibility() {
    const { passwordInput, passwordToggle } = this.dom;
    if (!passwordInput || !passwordToggle) return;
    const showPassword = passwordInput.type === 'password';
    passwordInput.type = showPassword ? 'text' : 'password';
    const icon = passwordToggle.querySelector('span');
    if (icon) icon.textContent = showPassword ? '🙈' : '👁️';
    passwordToggle.setAttribute(
      'aria-label',
      showPassword
        ? uiText('hide_password', '隐藏密码')
        : uiText('show_password', '显示密码'),
    );
  }

  async requestLogin(username, password) {
    const csrfToken = getCsrfToken();
    const headers = { 'Content-Type': 'application/json' };
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
    const response = await fetch(
      `/api/v1/auth/login?lang=${encodeURIComponent(currentPageLanguage())}`,
      {
        method: 'POST',
        credentials: 'same-origin',
        headers,
        body: JSON.stringify({ username, password }),
      },
    );
    let data;
    try {
      data = await response.json();
    } catch (_error) {
      throw new Error(uiText('auth_bad_server_data', '服务器返回无效数据'));
    }
    if (!response.ok || data.success !== true) {
      throw new Error(data.error || uiText('auth_verify_failed', '验证失败，请检查用户名和密码'));
    }
    return data;
  }

  async handleLogin() {
    const { usernameInput, passwordInput, loginBtn } = this.dom;
    if (!usernameInput || !passwordInput || !loginBtn || this.loginInProgress) return;
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    const validationError = validateCredentials(username, password);
    if (validationError) {
      this.showError(validationError);
      return;
    }
    this.hideError();
    this.setLoading(true);
    this.loginInProgress = true;
    try {
      const data = await this.requestLogin(username, password);
      const nextTarget = this.pendingRedirect;
      markLocalSessionActive();
      setAuthCookieHint(true);
      this.closeModal({ preserveRedirect: true });
      this.onLoginSuccess?.(data);
      this.pendingRedirect = null;
      if (nextTarget) window.location.href = nextTarget;
      else this.setLoading(false);
    } catch (error) {
      this.showError(error.message || uiText('auth_network_error', '网络错误'));
      this.setLoading(false);
    } finally {
      this.loginInProgress = false;
    }
  }

  setLoading(loading) {
    const button = this.dom.loginBtn;
    if (!button) return;
    button.toggleAttribute('aria-busy', loading);
    button.disabled = loading;
    button.classList.toggle('kawaii-button--loading', loading);
    const icon = button.querySelector('.btn-icon');
    const text = button.querySelector('.btn-text');
    if (icon) icon.textContent = loading ? '⏳' : '🔓';
    if (text) {
      text.textContent = loading
        ? uiText('auth_verify_loading', '验证中…')
        : uiText('auth_login', '登录');
    }
  }

  resetInputs() {
    if (this.dom.usernameInput) {
      this.dom.usernameInput.value = '';
      this.dom.usernameInput.type = 'text';
    }
    if (this.dom.passwordInput) {
      this.dom.passwordInput.value = '';
      this.dom.passwordInput.type = 'password';
    }
  }

  openModal(redirectHref = null) {
    if (!this.dom.modal) return;
    this.pendingRedirect = typeof redirectHref === 'string' && redirectHref.startsWith('/')
      ? redirectHref
      : null;
    const focusReturnId = this.prefix === 'console-' ? 'console-session-trigger' : 'user-trigger';
    this.dom.lastFocus = document.activeElement || document.getElementById(focusReturnId);
    this.dom.modal.hidden = false;
    this.dom.modal.setAttribute('role', 'dialog');
    this.dom.modal.setAttribute('aria-modal', 'true');
    const title = this.dom.modal.querySelector('.auth-modal-title, .console-auth-modal__title');
    if (title?.id) this.dom.modal.setAttribute('aria-labelledby', title.id);
    this.isModalOpen = true;
    document.body.classList.add('scroll-locked');
    document.addEventListener('click', this.handleClickOutside);
    document.addEventListener('keydown', this.handleKeyDown);
    this.resetInputs();
    clearTimeout(this.focusTimer);
    this.focusTimer = setTimeout(() => this.focusUsername(), 50);
    this.hideError();
  }

  focusUsername() {
    if (!window.matchMedia('(pointer: coarse)').matches) this.dom.usernameInput?.focus();
    this.focusTimer = null;
  }

  resetPasswordToggle() {
    const icon = this.dom.passwordToggle?.querySelector('span');
    if (icon) icon.textContent = '👁️';
    this.dom.passwordToggle?.setAttribute('aria-label', uiText('show_password', '显示密码'));
  }

  closeModal(options = {}) {
    if (!this.dom.modal) return;
    this.dom.modal.hidden = true;
    this.dom.modal.removeAttribute('aria-modal');
    this.dom.modal.removeAttribute('role');
    this.isModalOpen = false;
    document.body.classList.remove('scroll-locked');
    document.removeEventListener('click', this.handleClickOutside);
    document.removeEventListener('keydown', this.handleKeyDown);
    if (!options.preserveRedirect) this.pendingRedirect = null;
    this.hideError();
    this.setLoading(false);
    this.resetInputs();
    this.resetPasswordToggle();
    const explicitTrigger = this.closeHomePanel();
    clearTimeout(this.focusTimer);
    this.focusTimer = null;
    this.restoreFocus(explicitTrigger);
  }

  closeHomePanel() {
    if (this.prefix !== '') return null;
    const panel = document.getElementById('user-panel');
    const trigger = document.getElementById('user-trigger');
    if (panel) panel.hidden = true;
    trigger?.setAttribute('aria-expanded', 'false');
    return trigger;
  }

  restoreFocus(explicitTrigger) {
    const target = explicitTrigger || this.dom.lastFocus;
    this.dom.lastFocus = null;
    if (!target?.focus) return;
    setTimeout(() => {
      target.focus();
      setTimeout(() => target.focus(), 16);
    }, explicitTrigger ? 0 : 0);
  }

  handleKeyDown = (event) => {
    if (!this.isModalOpen) return;
    if (event.key === 'Escape') {
      event.stopImmediatePropagation();
      this.closeModal();
      return;
    }
    if (event.key === 'Tab') this.trapFocus(event);
  };

  trapFocus(event) {
    const selector = 'input, button, [href], select, textarea, [tabindex]:not([tabindex="-1"])';
    const focusables = Array.from(this.dom.modal.querySelectorAll(selector))
      .filter((element) => !element.disabled && !element.hidden && element.getClientRects().length);
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  handleClickOutside = (event) => {
    if (this.isModalOpen && event.target === this.dom.backdrop) {
      event.stopImmediatePropagation();
      this.closeModal();
    }
  };

  bindEvents() {
    this.dom.trigger?.addEventListener('click', () => this.openModal());
    this.dom.close?.addEventListener('click', () => this.closeModal());
    this.dom.cancel?.addEventListener('click', () => this.closeModal());
    const submit = (event) => {
      event.preventDefault();
      this.handleLogin();
    };
    (this.dom.form || this.dom.loginBtn)?.addEventListener(
      this.dom.form ? 'submit' : 'click',
      submit,
    );
    for (const input of [this.dom.usernameInput, this.dom.passwordInput]) {
      input?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') submit(event);
      });
      input?.addEventListener('input', () => this.hideError());
    }
    this.dom.passwordToggle?.addEventListener('click', () => this.togglePasswordVisibility());
  }
}

export function createAuthModalController(options) {
  const controller = new AuthModalController(options);
  return {
    openModal: (redirectHref) => controller.openModal(redirectHref),
    closeModal: (options) => controller.closeModal(options),
    isOpen: () => controller.isModalOpen,
    dom: controller.dom,
  };
}
