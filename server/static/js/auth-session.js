(() => {
  'use strict';

  const STORAGE_KEY = 'infinitas_auth_token';
  const EXPIRY_KEY = 'infinitas_auth_expiry';
  const DAYS_30 = 30 * 24 * 60 * 60 * 1000;
  const BG_STORAGE_KEY = 'infinitas_bg_settings';
  const shell = window.infinitasAppShell;
  const appSession = window.APP_SESSION || {};
  const sessionConfig = window.AUTH_SESSION_CONFIG || {};

  function currentPageLanguage() {
    return shell.currentPageLanguage();
  }

  function uiText(key, fallback) {
    return shell.uiText(key, fallback);
  }

  function uiTemplate(key, fallback, replacements = {}) {
    return shell.uiTemplate(key, fallback, replacements);
  }

  function markLocalSessionActive() {
    try {
      window.localStorage.setItem(EXPIRY_KEY, String(Date.now() + DAYS_30));
    } catch (_error) {
      // Ignore storage failures so cookie-backed auth can still work.
    }
  }

  function clearLocalSession() {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
      window.localStorage.removeItem(EXPIRY_KEY);
    } catch (_error) {
      // Ignore storage cleanup failures.
    }
  }

  function remainingDays() {
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

  function hasAuthCookieHint() {
    return appSession.has_auth_cookie_hint === true || appSession.hasAuthCookieHint === true;
  }

  function setAuthCookieHint(present) {
    appSession.has_auth_cookie_hint = present;
    appSession.hasAuthCookieHint = present;
  }

  function initialSessionUser() {
    const raw = appSession.current_user || appSession.currentUser;
    if (!raw || typeof raw.username !== 'string' || !raw.username) {
      return null;
    }
    return {
      username: raw.username,
      role: raw.role || null,
    };
  }

  async function requestSessionCleanup(logLabel) {
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

  function validateToken(token) {
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

  function createAuthModalController(options) {
    const {
      prefix = '',
      modalTitle = uiText('auth_modal_title', 'Authentication'),
      onLoginSuccess = null,
    } = options || {};

    const ids = {
      trigger: prefix + 'open-auth-modal-btn',
      modal: prefix + 'auth-modal',
      backdrop: prefix + 'auth-modal-backdrop',
      close: prefix + 'auth-modal-close',
      cancel: prefix + 'cancel-auth-btn',
      form: prefix + 'auth-form',
      input: prefix + 'token-input',
      toggle: prefix + 'token-toggle',
      error: prefix + 'auth-error',
      errorMessage: prefix + 'error-message',
      hint: prefix + 'token-hint',
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
      if (errorTimeout) clearTimeout(errorTimeout);
      errorTimeout = setTimeout(() => {
        if (dom.error) dom.error.hidden = true;
        errorTimeout = null;
      }, 5000);
    }

    function hideError() {
      if (!dom.error) return;
      dom.error.hidden = true;
      if (errorTimeout) {
        clearTimeout(errorTimeout);
        errorTimeout = null;
      }
    }

    function togglePasswordVisibility() {
      if (!dom.input || !dom.toggle) return;
      const isPassword = dom.input.type === 'password';
      dom.input.type = isPassword ? 'text' : 'password';
      const span = dom.toggle.querySelector('span');
      if (span) span.textContent = isPassword ? '🙈' : '👁️';
      dom.toggle.setAttribute('aria-label', isPassword ?
        uiText('hide_password', '隐藏密码') :
        uiText('show_password', '显示密码'));
    }

    async function handleLogin() {
      if (!dom.input || !dom.loginBtn || loginInProgress) return;
      const token = dom.input.value.trim();
      const validationError = validateToken(token);
      if (validationError) {
        showError(validationError);
        return;
      }

      hideError();
      setLoading(true);
      loginInProgress = true;

      try {
        const res = await fetch(`/api/auth/login?lang=${encodeURIComponent(currentPageLanguage())}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        let data;
        try {
          data = await res.json();
        } catch (_error) {
          throw new Error(uiText('auth_bad_server_data', '服务器返回无效数据'));
        }
        if (!res.ok || data.success !== true) {
          showError(data.error || uiText('auth_verify_failed', '验证失败，请检查访问令牌是否正确'));
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
        dom.loginBtn.classList.add('kawaii-button--loading');
        dom.loginBtn.style.opacity = '0.7';
        dom.loginBtn.style.pointerEvents = 'none';
        const icon = dom.loginBtn.querySelector('.btn-icon');
        const text = dom.loginBtn.querySelector('.btn-text');
        if (icon) icon.textContent = '⏳';
        if (text) text.textContent = uiText('auth_verify_loading', '验证中…');
      } else {
        dom.loginBtn.removeAttribute('aria-busy');
        dom.loginBtn.classList.remove('kawaii-button--loading');
        dom.loginBtn.style.opacity = '';
        dom.loginBtn.style.pointerEvents = '';
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
      document.body.style.overflow = 'hidden';
      document.addEventListener('click', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
      if (dom.input) {
        dom.input.value = '';
        dom.input.type = 'password';
        if (focusTimer) clearTimeout(focusTimer);
        focusTimer = setTimeout(() => {
          dom.input?.focus();
          focusTimer = null;
        }, 50);
      }
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
      document.body.style.overflow = '';
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
      if (!preserveRedirect) {
        pendingRedirect = null;
      }
      hideError();
      setLoading(false);
      if (dom.input) {
        dom.input.value = '';
        dom.input.type = 'password';
      }
      if (dom.toggle) {
        const span = dom.toggle.querySelector('span');
        if (span) span.textContent = '👁️';
        dom.toggle.setAttribute('aria-label', uiText('show_password', '显示密码'));
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
        if (dom.input) {
          dom.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleLogin();
            }
          });
        }
      }
      if (dom.input) dom.input.addEventListener('input', hideError);
      if (dom.toggle) dom.toggle.addEventListener('click', togglePasswordVisibility);
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

  function initHomeAuthSession() {
    const wrapper = document.getElementById('user-trigger-wrapper');
    const loginPanel = document.getElementById('login-panel');
    const standaloneLoginPage = !!loginPanel && !wrapper;
    if (!wrapper && !loginPanel) {
      return;
    }

    function parseHomeAuthData() {
      try {
        const el = document.getElementById('home-auth-session-data');
        return el && el.dataset.json ? JSON.parse(el.dataset.json) : {};
      } catch (_) { return {}; }
    }
    const homeConfig = parseHomeAuthData();
    const bgPresets = homeConfig.bgPresets || { light: [], dark: [] };
    let currentUser = initialSessionUser();
    let isUserPanelOpen = false;
    let bgObserver = null;

    function normalizeProtectedTarget(rawTarget) {
      if (typeof rawTarget !== 'string' || !rawTarget.startsWith('/')) {
        return null;
      }
      if (rawTarget.startsWith('//')) {
        return null;
      }
      return rawTarget;
    }

    function consumePendingAuthRedirect() {
      const url = new URL(window.location.href);
      if (url.searchParams.get('auth') !== 'required') {
        return null;
      }
      const target = normalizeProtectedTarget(url.searchParams.get('next'));
      url.searchParams.delete('auth');
      url.searchParams.delete('next');
      window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
      return target;
    }

    function openAuthModal(targetHref = null) {
      targetHref = normalizeProtectedTarget(targetHref);
      controller.openModal(targetHref);
    }

    const BackgroundManager = {
      getSettings() {
        try {
          const saved = window.localStorage.getItem(BG_STORAGE_KEY);
          if (saved) {
            return JSON.parse(saved);
          }
        } catch (error) {
          console.error('Failed to parse background settings:', error);
        }
        return { light: null, dark: null };
      },
      saveSettings(settings) {
        try {
          window.localStorage.setItem(BG_STORAGE_KEY, JSON.stringify(settings));
        } catch (_error) {
          // Ignore storage failures for local preference persistence.
        }
      },
      getCurrentBgId(theme) {
        const settings = BackgroundManager.getSettings();
        return settings[theme] || null;
      },
      setCurrentBgId(theme, bgId) {
        const settings = BackgroundManager.getSettings();
        settings[theme] = bgId;
        BackgroundManager.saveSettings(settings);
      },
      apply(theme, bgId) {
        const preset = (bgPresets[theme] || []).find((item) => item.id === bgId);
        const variableName = theme === 'dark' ? '--bg-image-dark' : '--bg-image';
        if (!preset) {
          document.body.style.removeProperty(variableName);
          return;
        }
        const lightGradient = getComputedStyle(document.body).getPropertyValue('--bg-gradient-light').trim() || 'linear-gradient(135deg, rgba(255, 240, 245, 0.92) 0%, rgba(255, 228, 235, 0.88) 50%, rgba(255, 248, 250, 0.92) 100%)';
        const darkGradient = getComputedStyle(document.body).getPropertyValue('--bg-gradient-dark').trim() || 'linear-gradient(135deg, rgba(15, 10, 25, 0.92) 0%, rgba(25, 15, 35, 0.9) 50%, rgba(20, 10, 30, 0.92) 100%)';
        if (preset.url) {
          const gradient = theme === 'light' ? lightGradient : darkGradient;
          const safeUrl = preset.url.replace(/['()\\]/g, '\\$&');
          document.body.style.setProperty(variableName, `${gradient}, url('${safeUrl}')`);
          return;
        }
        document.body.style.removeProperty(variableName);
      },
      renderSelector(theme) {
        const grid = document.getElementById('bg-grid');
        const themeLabel = document.getElementById('bg-theme-label');
        if (!grid) {
          return;
        }
        const currentBgId = BackgroundManager.getCurrentBgId(theme);
        const presets = bgPresets[theme] || [];
        if (themeLabel) {
          themeLabel.textContent = theme === 'light'
            ? uiText('user_panel_theme_light', '浅色')
            : uiText('user_panel_theme_dark', '深色');
        }
        grid.replaceChildren();
        presets.forEach((preset) => {
          const isActive = preset.id === currentBgId;
          const gradientClass = preset.url ? '' : 'bg-option--gradient';
          const btn = document.createElement('button');
          btn.className = `bg-option ${gradientClass} ${isActive ? 'is-active' : ''}`;
          btn.dataset.bgId = preset.id;
          btn.dataset.name = preset.name;
          btn.type = 'button';
          btn.setAttribute('aria-label', preset.name);
          btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
          if (preset.url) {
            const safeUrl = preset.url.replace(/['()\\]/g, '\\$&');
            btn.style.backgroundImage = `url('${safeUrl}')`;
          }
          grid.appendChild(btn);
        });
        if (!grid.dataset.delegateBound) {
          grid.dataset.delegateBound = 'true';
          grid.addEventListener('click', (e) => {
            const button = e.target.closest('.bg-option');
            if (!button) return;
            const currentTheme = document.documentElement.getAttribute('data-color-scheme') || 'light';
            handleBgSelect(currentTheme, button.dataset.bgId);
          });
        }
      },
      init() {
        const currentTheme = document.documentElement.getAttribute('data-color-scheme') || 'light';
        const currentBgId = BackgroundManager.getCurrentBgId(currentTheme);
        if (currentBgId) {
          BackgroundManager.apply(currentTheme, currentBgId);
        }
        bgObserver = new MutationObserver((mutations) => {
          mutations.forEach((mutation) => {
            if (mutation.attributeName !== 'data-color-scheme') {
              return;
            }
            const theme = document.documentElement.getAttribute('data-color-scheme') || 'light';
            const bgId = BackgroundManager.getCurrentBgId(theme);
            BackgroundManager.apply(theme, bgId);
            if (isUserPanelOpen) {
              BackgroundManager.renderSelector(theme);
            }
          });
        });
        bgObserver.observe(document.documentElement, { attributes: true });
        window.addEventListener('beforeunload', () => {
          if (bgObserver) bgObserver.disconnect();
        });
      },
    };

    async function handleBgSelect(theme, bgId) {
      BackgroundManager.apply(theme, bgId);
      BackgroundManager.setCurrentBgId(theme, bgId);
      if (currentUser) {
        try {
          const response = await fetch('/api/background/set', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ theme, bg_id: bgId }),
          });
          if (!response.ok) {
            console.error('Failed to save background to server');
          }
        } catch (error) {
          console.error('Network error saving background:', error);
        }
      }
      const grid = document.getElementById('bg-grid');
      if (!grid) {
        return;
      }
      grid.querySelectorAll('.bg-option').forEach((button) => {
        button.classList.remove('is-active');
        button.setAttribute('aria-pressed', 'false');
      });
      const activeButton = grid.querySelector(`[data-bg-id="${CSS.escape(bgId)}"]`);
      if (activeButton) {
        activeButton.classList.add('is-active');
        activeButton.setAttribute('aria-pressed', 'true');
      }
    }

    function updateUserTriggerIcon(isLoggedIn) {
      const icon = document.getElementById('user-trigger-icon');
      const pulse = document.getElementById('user-trigger-pulse');
      const trigger = document.getElementById('user-trigger');
      if (icon) {
        icon.textContent = isLoggedIn ? '👤' : '🔒';
      }
      if (pulse) {
        pulse.hidden = isLoggedIn;
      }
      if (trigger) {
        trigger.classList.toggle('is-active', isLoggedIn);
        trigger.setAttribute(
          'aria-label',
          isLoggedIn
            ? uiText('user_menu_logged_label', '已登录用户菜单')
            : uiText('user_menu_anon_label', '登录')
        );
      }
    }

    function formatSessionMeta() {
      const days = remainingDays();
      if (days > 0) {
        return uiTemplate('auth_expiry_days', '{days} 天后过期', { days });
      }
      return uiText('auth_session_active', '会话已连接');
    }

    function updateUserPanelState() {
      const loginSection = document.getElementById('user-panel-login');
      const loggedSection = document.getElementById('user-panel-logged');
      if (currentUser) {
        if (loginSection) {
          loginSection.hidden = true;
        }
        if (loggedSection) {
          loggedSection.hidden = false;
        }
        const username = document.getElementById('user-panel-username');
        const expiry = document.getElementById('user-panel-expiry');
        const avatar = document.getElementById('user-avatar');
        if (username) {
          username.textContent = currentUser.username;
        }
        if (expiry) {
          expiry.textContent = formatSessionMeta();
        }
        if (avatar) {
          avatar.textContent = currentUser.username.charAt(0).toUpperCase();
        }
        const theme = document.documentElement.getAttribute('data-color-scheme') || 'light';
        BackgroundManager.renderSelector(theme);
      } else {
        if (loginSection) {
          loginSection.hidden = false;
        }
        if (loggedSection) {
          loggedSection.hidden = true;
        }
      }
    }

    function closeUserPanel() {
      const panel = document.getElementById('user-panel');
      const trigger = document.getElementById('user-trigger');
      if (!panel || panel.hidden) {
        return;
      }
      isUserPanelOpen = false;
      panel.hidden = true;
      if (trigger) {
        trigger.setAttribute('aria-expanded', 'false');
      }
    }

    function toggleUserPanel() {
      const panel = document.getElementById('user-panel');
      const trigger = document.getElementById('user-trigger');
      if (!panel || !trigger) {
        return;
      }
      isUserPanelOpen = !isUserPanelOpen;
      panel.hidden = !isUserPanelOpen;
      trigger.setAttribute('aria-expanded', String(isUserPanelOpen));
      if (isUserPanelOpen && currentUser) {
        const theme = document.documentElement.getAttribute('data-color-scheme') || 'light';
        BackgroundManager.renderSelector(theme);
      }
    }

    async function fetchAndApplyUserBackground() {
      try {
        const response = await fetch('/api/background/me', { credentials: 'same-origin' });
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        const theme = document.documentElement.getAttribute('data-color-scheme') || 'light';
        if (payload.light_bg_id) {
          BackgroundManager.setCurrentBgId('light', payload.light_bg_id);
          if (theme === 'light') {
            BackgroundManager.apply('light', payload.light_bg_id);
          }
        }
        if (payload.dark_bg_id) {
          BackgroundManager.setCurrentBgId('dark', payload.dark_bg_id);
          if (theme === 'dark') {
            BackgroundManager.apply('dark', payload.dark_bg_id);
          }
        }
      } catch (error) {
        console.error('Failed to fetch background:', error);
      }
    }

    async function initAuthState() {
      const shouldProbeAuth = hasAuthCookieHint() || remainingDays() > 0;
      if (currentUser) {
        setAuthCookieHint(true);
        await fetchAndApplyUserBackground();
        return;
      }
      if (!shouldProbeAuth) {
        clearLocalSession();
        currentUser = null;
        updateUserTriggerIcon(false);
        updateUserPanelState();
        return;
      }
      try {
        const response = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (response.ok) {
          const payload = await response.json();
          if (payload.authenticated) {
            setAuthCookieHint(true);
            currentUser = { username: payload.username, role: payload.role || null };
            updateUserTriggerIcon(true);
            updateUserPanelState();
            await fetchAndApplyUserBackground();
            return;
          }
        }
      } catch (error) {
        console.error('Auth validation failed:', error);
      }
      await requestSessionCleanup('Failed to clear auth cookie on server:');
      clearLocalSession();
      currentUser = null;
      updateUserTriggerIcon(false);
      updateUserPanelState();
    }

    async function handleLogout() {
      clearLocalSession();
      await requestSessionCleanup('Failed to clear auth cookie on server:');
      currentUser = null;
      updateUserTriggerIcon(false);
      updateUserPanelState();
      closeUserPanel();
      document.body.style.removeProperty('--bg-image');
      document.body.style.removeProperty('--bg-image-dark');
      document.dispatchEvent(new CustomEvent('infinitas:auth-changed', { detail: { authenticated: false } }));
    }

    function handleClickOutside(event) {
      if (wrapper && !wrapper.contains(event.target) && isUserPanelOpen) {
        closeUserPanel();
      }
    }

    function handleKeyDown(event) {
      if (event.key !== 'Escape') {
        return;
      }
      if (isUserPanelOpen) {
        closeUserPanel();
      }
    }

    function handleProtectedNavigation(event) {
      const link = event.target.closest('[data-auth-required="true"]');
      if (!link) return;
      if (currentUser) {
        return;
      }
      event.preventDefault();
      const targetHref = link.dataset.authTarget || link.getAttribute('href') || null;
      openAuthModal(targetHref);
    }

    function bindEvents() {
      document.getElementById('user-trigger')?.addEventListener('click', toggleUserPanel);
      document.getElementById('logout-btn')?.addEventListener('click', handleLogout);
      document.querySelectorAll('[data-auth-required="true"]').forEach((link) => {
        link.setAttribute('aria-haspopup', 'dialog');
      });
      document.body.addEventListener('click', handleProtectedNavigation);
      document.addEventListener('click', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }

    const authPrefix = standaloneLoginPage ? 'login-' : '';
    const controller = createAuthModalController({
      prefix: authPrefix,
      modalTitle: uiText('auth_modal_title', 'Authentication'),
      onLoginSuccess: (data) => {
        currentUser = { username: data.username, role: data.role || null };
        updateUserTriggerIcon(true);
        updateUserPanelState();
        document.dispatchEvent(new CustomEvent('infinitas:auth-changed', { detail: { authenticated: true, username: data.username, role: data.role } }));
        if (standaloneLoginPage) {
          window.location.href = sessionConfig.homeHref || '/';
        }
      },
    });

    async function init() {
      BackgroundManager.init();
      updateUserTriggerIcon(!!currentUser);
      updateUserPanelState();
      await initAuthState();
      if (standaloneLoginPage && currentUser) {
        window.location.replace(sessionConfig.homeHref || '/');
        return;
      }
      bindEvents();
      const homeAuthModalStartsVisible = !standaloneLoginPage && controller.dom.modal && !controller.dom.modal.hidden;
      if (homeAuthModalStartsVisible) {
        openAuthModal();
      }
      const protectedTarget = consumePendingAuthRedirect();
      if (!protectedTarget) {
        return;
      }
      if (currentUser) {
        window.location.replace(protectedTarget);
        return;
      }
      openAuthModal(protectedTarget);
    }

    window.openHomeAuthModal = openAuthModal;
    init();
  }

  function initConsoleAuthSession() {
    const root = document.getElementById('console-session-root');
    if (!root) {
      return;
    }

    let currentUser = initialSessionUser();
    let panelOpen = false;

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
      window.location.href = sessionConfig.homeHref || '/';
    }

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

    const controller = createAuthModalController({
      prefix: 'console-',
      modalTitle: uiText('console_auth_modal_title', 'Identity check'),
      onLoginSuccess: (data) => {
        currentUser = { username: data.username, role: data.role || null };
        renderSessionState();
        if (window.toast) {
          window.toast.success(uiText('auth_session_active', 'Session active'));
        }
      },
    });

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
  function initAll() {
    initHomeAuthSession();
    initConsoleAuthSession();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
