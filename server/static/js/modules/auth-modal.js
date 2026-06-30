/**
 * Reusable authentication modal controller factory.
 *
 * Creates an object that manages a login modal (DOM caching, event binding,
 * password toggle, keyboard trapping, focus management, and the login fetch).
 * The returned controller exposes `openModal`, `closeModal`, `isOpen`, and
 * `dom` so that callers (auth-home, auth-console) can drive it externally.
 */

import {
  currentPageLanguage,
  uiText,
  validateCredentials,
  markLocalSessionActive,
  setAuthCookieHint,
  getCsrfToken,
} from './auth-shared.js';

/**
 * Create a new auth-modal controller bound to the DOM elements whose IDs are
 * derived from `prefix`.
 *
 * @param {object}  options
 * @param {string}  [options.prefix='']           ID prefix for all DOM elements.
 * @param {string}  [options.modalTitle]           Ignored (kept for API compat).
 * @param {function|null} [options.onLoginSuccess] Called with (data) on success.
 * @returns {{ openModal, closeModal, isOpen, dom }}
 */
export function createAuthModalController(options) {
  const {
    prefix = '',
    onLoginSuccess = null,
  } = options || {};

  const ids = {
    trigger: prefix + 'open-auth-modal-btn',
    modal: prefix + 'auth-modal',
    backdrop: prefix + 'auth-modal-backdrop',
    close: prefix + 'auth-modal-close',
    cancel: prefix + 'cancel-auth-btn',
    form: prefix + 'auth-form',
    usernameInput: prefix + 'username-input',
    passwordInput: prefix + 'password-input',
    passwordToggle: prefix + 'password-toggle',
    error: prefix + 'auth-error',
    errorMessage: prefix + 'error-message',
    hint: prefix + 'auth-hint',
    loginBtn: prefix + 'login-btn',
  };

  let isOpen = false;
  let loginInProgress = false;
  let pendingRedirect = null;
  let errorTimeout = null;
  let focusTimer = null;

  const dom = {};

  function getElement(id) {
    return document.getElementById(id);
  }

  function cacheElements() {
    Object.keys(ids).forEach((key) => {
      dom[key] = getElement(ids[key]);
    });
  }

  function showError(message) {
    if (!dom.errorMessage || !dom.error) return;
    dom.errorMessage.textContent = message;
    dom.error.hidden = false;
    if (dom.usernameInput) {
      dom.usernameInput.setAttribute('aria-invalid', 'true');
    }
    if (dom.passwordInput) {
      dom.passwordInput.setAttribute('aria-invalid', 'true');
    }
    if (errorTimeout) clearTimeout(errorTimeout);
    errorTimeout = setTimeout(() => {
      if (dom.error) dom.error.hidden = true;
      errorTimeout = null;
    }, 5000);
  }

  function hideError() {
    if (!dom.error) return;
    dom.error.hidden = true;
    if (dom.usernameInput) {
      dom.usernameInput.removeAttribute('aria-invalid');
    }
    if (dom.passwordInput) {
      dom.passwordInput.removeAttribute('aria-invalid');
    }
    if (errorTimeout) {
      clearTimeout(errorTimeout);
      errorTimeout = null;
    }
  }

  function togglePasswordVisibility() {
    if (!dom.passwordInput || !dom.passwordToggle) return;
    const isPassword = dom.passwordInput.type === 'password';
    dom.passwordInput.type = isPassword ? 'text' : 'password';
    const span = dom.passwordToggle.querySelector('span');
    if (span) span.textContent = isPassword ? '🙈' : '👁️';
    dom.passwordToggle.setAttribute('aria-label', isPassword ?
      uiText('hide_password', '隐藏密码') :
      uiText('show_password', '显示密码'));
  }

  async function handleLogin() {
    if (!dom.usernameInput || !dom.passwordInput || !dom.loginBtn || loginInProgress) return;
    const username = dom.usernameInput.value.trim();
    const password = dom.passwordInput.value;
    const validationError = validateCredentials(username, password);
    if (validationError) {
      showError(validationError);
      return;
    }

    hideError();
    setLoading(true);
    loginInProgress = true;

    try {
      const csrfToken = getCsrfToken();
      const res = await fetch(`/api/v1/auth/login?lang=${encodeURIComponent(currentPageLanguage())}`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: csrfToken ? { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken } : { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      let data;
      try {
        data = await res.json();
      } catch (_error) {
        throw new Error(uiText('auth_bad_server_data', '服务器返回无效数据'));
      }
      if (!res.ok || data.success !== true) {
        showError(data.error || uiText('auth_verify_failed', '验证失败，请检查用户名和密码'));
        setLoading(false);
        return;
      }
      const nextTarget = pendingRedirect;
      markLocalSessionActive();
      setAuthCookieHint(true);
      closeModal({ preserveRedirect: true });
      if (typeof onLoginSuccess === 'function') {
        onLoginSuccess(data);
      }
      pendingRedirect = null;
      if (nextTarget) {
        window.location.href = nextTarget;
      } else {
        setLoading(false);
      }
    } catch (e) {
      showError(e.message || uiText('auth_network_error', '网络错误'));
      setLoading(false);
    } finally {
      loginInProgress = false;
    }
  }

  function setLoading(loading) {
    if (!dom.loginBtn) return;
    if (loading) {
      dom.loginBtn.setAttribute('aria-busy', 'true');
      dom.loginBtn.disabled = true;
      dom.loginBtn.classList.add('kawaii-button--loading');
      const icon = dom.loginBtn.querySelector('.btn-icon');
      const text = dom.loginBtn.querySelector('.btn-text');
      if (icon) icon.textContent = '⏳';
      if (text) text.textContent = uiText('auth_verify_loading', '验证中…');
    } else {
      dom.loginBtn.removeAttribute('aria-busy');
      dom.loginBtn.disabled = false;
      dom.loginBtn.classList.remove('kawaii-button--loading');
      const icon = dom.loginBtn.querySelector('.btn-icon');
      const text = dom.loginBtn.querySelector('.btn-text');
      if (icon) icon.textContent = '🔓';
      if (text) text.textContent = uiText('auth_login', '登录');
    }
  }

  function openModal(redirectHref = null) {
    if (!dom.modal) return;
    pendingRedirect = (typeof redirectHref === 'string' && redirectHref.startsWith('/')) ? redirectHref : null;
    const focusReturnId = prefix === 'console-' ? 'console-session-trigger' : 'user-trigger';
    dom.lastFocus = document.activeElement || document.getElementById(focusReturnId);
    dom.modal.hidden = false;
    dom.modal.setAttribute('role', 'dialog');
    dom.modal.setAttribute('aria-modal', 'true');
    const title = dom.modal.querySelector('.auth-modal-title, .console-auth-modal__title');
    if (title && title.id) {
      dom.modal.setAttribute('aria-labelledby', title.id);
    }
    isOpen = true;
    document.body.classList.add('scroll-locked');
    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    if (dom.usernameInput) {
      dom.usernameInput.value = '';
      dom.usernameInput.type = 'text';
    }
    if (dom.passwordInput) {
      dom.passwordInput.value = '';
      dom.passwordInput.type = 'password';
    }
    if (focusTimer) clearTimeout(focusTimer);
    focusTimer = setTimeout(() => {
      // Avoid autofocus on touch devices to prevent virtual keyboard from hijacking viewport
      const isTouchDevice = window.matchMedia('(pointer: coarse)').matches;
      if (!isTouchDevice && dom.usernameInput) {
        dom.usernameInput.focus();
      }
      focusTimer = null;
    }, 50);
    hideError();
  }

  function closeModal(options = {}) {
    const { preserveRedirect = false } = options;
    let explicitHomeTrigger = null;
    if (!dom.modal) return;
    dom.modal.hidden = true;
    dom.modal.removeAttribute('aria-modal');
    dom.modal.removeAttribute('role');
    isOpen = false;
    document.body.classList.remove('scroll-locked');
    document.removeEventListener('click', handleClickOutside);
    document.removeEventListener('keydown', handleKeyDown);
    if (!preserveRedirect) {
      pendingRedirect = null;
    }
    hideError();
    setLoading(false);
    if (dom.usernameInput) {
      dom.usernameInput.value = '';
    }
    if (dom.passwordInput) {
      dom.passwordInput.value = '';
      dom.passwordInput.type = 'password';
    }
    if (dom.passwordToggle) {
      const span = dom.passwordToggle.querySelector('span');
      if (span) span.textContent = '👁️';
      dom.passwordToggle.setAttribute('aria-label', uiText('show_password', '显示密码'));
    }
    if (prefix === '') {
      const homePanel = document.getElementById('user-panel');
      const homeTrigger = document.getElementById('user-trigger');
      if (homePanel) homePanel.hidden = true;
      if (homeTrigger) {
        homeTrigger.setAttribute('aria-expanded', 'false');
        explicitHomeTrigger = homeTrigger;
      }
    }
    if (focusTimer) {
      clearTimeout(focusTimer);
      focusTimer = null;
    }
    if (explicitHomeTrigger && explicitHomeTrigger.focus) {
      explicitHomeTrigger.focus();
      setTimeout(() => explicitHomeTrigger.focus(), 16);
      dom.lastFocus = null;
    } else if (dom.lastFocus && dom.lastFocus.focus) {
      const nextFocus = dom.lastFocus;
      dom.lastFocus = null;
      setTimeout(() => {
        nextFocus.focus();
        setTimeout(() => nextFocus.focus(), 16);
      }, 0);
    }
  }

  function handleKeyDown(event) {
    if (!isOpen) return;
    if (event.key === 'Escape') {
      event.stopImmediatePropagation();
      closeModal();
      return;
    }
    if (event.key === 'Tab') {
      const focusables = Array.from(dom.modal.querySelectorAll('input, button, [href], select, textarea, [tabindex]:not([tabindex="-1"])')).filter((el) => !el.disabled && !el.hidden && el.getClientRects().length > 0);
      if (focusables.length === 0) return;
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
  }

  function handleClickOutside(event) {
    if (!isOpen || !dom.backdrop) return;
    if (event.target === dom.backdrop) {
      event.stopImmediatePropagation();
      closeModal();
    }
  }

  function bindEvents() {
    if (dom.trigger) dom.trigger.addEventListener('click', () => openModal());
    if (dom.close) dom.close.addEventListener('click', () => closeModal());
    if (dom.cancel) dom.cancel.addEventListener('click', () => closeModal());

    if (dom.form) {
      dom.form.addEventListener('submit', (e) => {
        e.preventDefault();
        handleLogin();
      });
    } else {
      if (dom.loginBtn) {
        dom.loginBtn.addEventListener('click', (e) => {
          e.preventDefault();
          handleLogin();
        });
      }
    }
    if (dom.usernameInput) {
      dom.usernameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          handleLogin();
        }
      });
      dom.usernameInput.addEventListener('input', hideError);
    }
    if (dom.passwordInput) {
      dom.passwordInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          handleLogin();
        }
      });
      dom.passwordInput.addEventListener('input', hideError);
    }
    if (dom.passwordToggle) dom.passwordToggle.addEventListener('click', togglePasswordVisibility);
  }

  cacheElements();
  bindEvents();

  return {
    openModal,
    closeModal,
    isOpen: () => isOpen,
    dom,
  };
}
