(() => {
  'use strict';

  const STORAGE_KEY = 'infinitas_auth_token';
  const EXPIRY_KEY = 'infinitas_auth_expiry';
  const DAYS_30 = 30 * 24 * 60 * 60 * 1000;
  const BG_STORAGE_KEY = 'infinitas_bg_settings';
  const shell = window.infinitasAppShell || {};
  const appSession = window.APP_SESSION || {};
  const sessionConfig = window.AUTH_SESSION_CONFIG || {};

  function currentPageLanguage() {
    if (typeof shell.currentPageLanguage === 'function') {
      return shell.currentPageLanguage();
    }
    const lang = (document.documentElement.lang || '').toLowerCase();
    return lang.startsWith('en') ? 'en' : 'zh';
  }

  function uiText(key, fallback) {
    if (typeof shell.uiText === 'function') {
      return shell.uiText(key, fallback);
    }
    const value = (window.APP_UI || {})[key];
    return typeof value === 'string' && value ? value : fallback;
  }

  function uiTemplate(key, fallback, replacements = {}) {
    if (typeof shell.uiTemplate === 'function') {
      return shell.uiTemplate(key, fallback, replacements);
    }
    let template = uiText(key, fallback);
    Object.entries(replacements).forEach(([name, value]) => {
      template = template.replace(`{${name}}`, String(value));
    });
    return template;
  }

  function saveLocalSession() {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
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
      await fetch('/api/auth/logout', { method: 'POST' });
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

  function initHomeAuthSession() {
    const wrapper = document.getElementById('user-trigger-wrapper');
    if (!wrapper) {
      return;
    }

    const homeConfig = window.HOME_AUTH_SESSION_CONFIG || {};
    const bgPresets = homeConfig.bgPresets || { light: [], dark: [] };
    let currentUser = initialSessionUser();
    let isUserPanelOpen = false;
    let isAuthModalOpen = false;
    let pendingAuthTarget = null;
    let lastAuthTrigger = null;
    let errorTimeout = null;

    function normalizeProtectedTarget(rawTarget) {
      if (typeof rawTarget !== 'string' || !rawTarget.startsWith('/')) {
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
        const lightGradient = 'linear-gradient(135deg, rgba(255, 240, 245, 0.88) 0%, rgba(255, 228, 235, 0.82) 50%, rgba(255, 248, 250, 0.88) 100%)';
        const darkGradient = 'linear-gradient(135deg, rgba(15, 10, 25, 0.88) 0%, rgba(25, 15, 35, 0.85) 50%, rgba(20, 10, 30, 0.88) 100%)';
        if (preset.url) {
          const gradient = theme === 'light' ? lightGradient : darkGradient;
          document.body.style.setProperty(variableName, `${gradient}, url('${preset.url}')`);
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
        const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (match) => ({
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;',
        }[match]));
        grid.innerHTML = presets.map((preset) => {
          const isActive = preset.id === currentBgId;
          const bgStyle = preset.url ? `background-image: url('${preset.url}')` : '';
          const gradientClass = preset.url ? '' : 'bg-option--gradient';
          return `<button class="bg-option ${gradientClass} ${isActive ? 'is-active' : ''}" data-bg-id="${preset.id}" data-name="${escapeHtml(preset.name)}" type="button" aria-label="${escapeHtml(preset.name)}" aria-pressed="${isActive ? 'true' : 'false'}" style="${bgStyle}"></button>`;
        }).join('');
        grid.querySelectorAll('.bg-option').forEach((button) => {
          button.addEventListener('click', () => handleBgSelect(theme, button.dataset.bgId));
        });
      },
      init() {
        const currentTheme = document.documentElement.getAttribute('data-color-scheme') || 'light';
        const currentBgId = BackgroundManager.getCurrentBgId(currentTheme);
        if (currentBgId) {
          BackgroundManager.apply(currentTheme, currentBgId);
        }
        const observer = new MutationObserver((mutations) => {
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
        observer.observe(document.documentElement, { attributes: true });
      },
    };

    async function handleBgSelect(theme, bgId) {
      BackgroundManager.apply(theme, bgId);
      BackgroundManager.setCurrentBgId(theme, bgId);
      if (currentUser) {
        try {
          const response = await fetch('/api/background/set', {
            method: 'POST',
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
      const activeButton = grid.querySelector(`[data-bg-id="${bgId}"]`);
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

    function setLoading(loading) {
      const button = document.getElementById('login-btn');
      if (!button) {
        return;
      }
      const icon = button.querySelector('.btn-icon');
      const text = button.querySelector('.btn-text');
      button.disabled = loading;
      button.classList.toggle('kawaii-button--loading', loading);
      if (icon) {
        icon.textContent = loading ? '⏳' : '🔓';
      }
      if (text) {
        text.textContent = loading
          ? uiText('auth_verify_loading', '验证中...')
          : uiText('auth_verify', '验证');
      }
    }

    function hideError() {
      const errorBox = document.getElementById('auth-error');
      if (errorBox) {
        errorBox.hidden = true;
      }
      if (errorTimeout) {
        clearTimeout(errorTimeout);
        errorTimeout = null;
      }
    }

    function showError(message) {
      const errorBox = document.getElementById('auth-error');
      const errorMessage = document.getElementById('error-message');
      if (!errorBox || !errorMessage) {
        return;
      }
      errorMessage.textContent = message;
      errorBox.hidden = false;
      if (errorTimeout) {
        clearTimeout(errorTimeout);
      }
      errorTimeout = window.setTimeout(() => {
        errorBox.hidden = true;
        errorTimeout = null;
      }, 5000);
    }

    function resolveAuthReturnTarget() {
      const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (!active) {
        return null;
      }
      if (active.closest('#user-panel')) {
        return document.getElementById('user-trigger');
      }
      return active;
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

    function openAuthModal(targetHref = null) {
      const modal = document.getElementById('auth-modal');
      if (!modal) {
        return;
      }
      lastAuthTrigger = resolveAuthReturnTarget();
      pendingAuthTarget = targetHref;
      isAuthModalOpen = true;
      modal.hidden = false;
      document.body.style.overflow = 'hidden';
      closeUserPanel();
      window.setTimeout(() => {
        const input = document.getElementById('token-input');
        if (input) {
          input.focus();
        }
      }, 100);
    }

    function closeAuthModal(clearPendingTarget = true) {
      const modal = document.getElementById('auth-modal');
      if (!modal) {
        return;
      }
      isAuthModalOpen = false;
      modal.hidden = true;
      document.body.style.overflow = '';
      if (clearPendingTarget) {
        pendingAuthTarget = null;
      }
      const input = document.getElementById('token-input');
      if (input) {
        input.value = '';
      }
      hideError();
      setLoading(false);
      if (lastAuthTrigger && typeof lastAuthTrigger.focus === 'function' && document.contains(lastAuthTrigger)) {
        window.setTimeout(() => {
          if (document.contains(lastAuthTrigger)) {
            lastAuthTrigger.focus();
          }
        }, 0);
      }
    }

    async function syncBackgroundToServer() {
      if (!currentUser) {
        return;
      }
      const settings = BackgroundManager.getSettings();
      try {
        if (settings.light) {
          await fetch('/api/background/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ theme: 'light', bg_id: settings.light }),
          });
        }
        if (settings.dark) {
          await fetch('/api/background/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ theme: 'dark', bg_id: settings.dark }),
          });
        }
      } catch (error) {
        console.error('Failed to sync background:', error);
      }
    }

    async function fetchAndApplyUserBackground() {
      try {
        const response = await fetch('/api/background/me');
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
        const response = await fetch('/api/auth/me');
        if (response.ok) {
          const payload = await response.json();
          if (payload.authenticated) {
            setAuthCookieHint(true);
            currentUser = { username: payload.username };
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

    async function handleLogin() {
      const input = document.getElementById('token-input');
      if (!input) {
        return;
      }
      const token = input.value.trim();
      const validationError = validateToken(token);
      if (validationError) {
        showError(validationError);
        return;
      }
      hideError();
      setLoading(true);
      try {
        const response = await fetch(`/api/auth/login?lang=${currentPageLanguage()}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        let payload;
        try {
          payload = await response.json();
        } catch (_error) {
          throw new Error(uiText('auth_bad_server_data', '服务器返回无效数据'));
        }
        if (!response.ok || payload.success !== true) {
          showError(payload.error || uiText('auth_verify_failed', '验证失败，请检查访问令牌是否正确'));
          return;
        }
        saveLocalSession();
        setAuthCookieHint(true);
        currentUser = { username: payload.username };
        updateUserTriggerIcon(true);
        updateUserPanelState();
        const nextTarget = pendingAuthTarget;
        closeAuthModal(false);
        await syncBackgroundToServer();
        pendingAuthTarget = null;
        if (nextTarget) {
          window.location.href = nextTarget;
        }
      } catch (error) {
        showError(error.message || uiText('auth_network_error', '网络错误，请检查网络连接后重试'));
      } finally {
        setLoading(false);
      }
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
    }

    function togglePasswordVisibility() {
      const input = document.getElementById('token-input');
      const toggle = document.getElementById('token-toggle');
      if (!input || !toggle) {
        return;
      }
      const revealing = input.type === 'password';
      input.type = revealing ? 'text' : 'password';
      const icon = toggle.querySelector('span');
      if (icon) {
        icon.textContent = revealing ? '🙈' : '👁️';
      }
      toggle.setAttribute(
        'aria-label',
        revealing ? uiText('hide_password', '隐藏密码') : uiText('show_password', '显示密码')
      );
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
      if (isAuthModalOpen) {
        closeAuthModal();
        return;
      }
      if (isUserPanelOpen) {
        closeUserPanel();
      }
    }

    function handleProtectedNavigation(event) {
      if (currentUser) {
        return;
      }
      event.preventDefault();
      const link = event.currentTarget;
      const targetHref = link.dataset.authTarget || link.getAttribute('href') || null;
      openAuthModal(targetHref);
    }

    function bindEvents() {
      document.getElementById('user-trigger')?.addEventListener('click', toggleUserPanel);
      document.getElementById('open-auth-modal-btn')?.addEventListener('click', () => openAuthModal());
      document.getElementById('auth-modal-close')?.addEventListener('click', () => closeAuthModal());
      document.getElementById('cancel-auth-btn')?.addEventListener('click', () => closeAuthModal());
      document.getElementById('auth-modal-backdrop')?.addEventListener('click', () => closeAuthModal());
      document.getElementById('auth-form')?.addEventListener('submit', (event) => {
        event.preventDefault();
        handleLogin();
      });
      document.getElementById('token-input')?.addEventListener('input', hideError);
      document.getElementById('token-toggle')?.addEventListener('click', togglePasswordVisibility);
      document.getElementById('logout-btn')?.addEventListener('click', handleLogout);
      document.querySelectorAll('[data-auth-required="true"]').forEach((link) => {
        link.addEventListener('click', handleProtectedNavigation);
      });
      document.addEventListener('click', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }

    async function init() {
      BackgroundManager.init();
      updateUserTriggerIcon(!!currentUser);
      updateUserPanelState();
      await initAuthState();
      bindEvents();
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

    window.openAuthModal = openAuthModal;
    init();
  }

  function initConsoleAuthSession() {
    const root = document.getElementById('console-session-root');
    if (!root) {
      return;
    }

    let currentUser = initialSessionUser();
    let panelOpen = false;
    let modalOpen = false;
    let pendingTarget = null;
    let lastTrigger = null;
    let errorTimeout = null;

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
        icon.textContent = authenticated ? '👤' : '🔒';
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

    function hideError() {
      const errorBox = document.getElementById('console-auth-error');
      if (errorBox) {
        errorBox.hidden = true;
      }
      if (errorTimeout) {
        clearTimeout(errorTimeout);
        errorTimeout = null;
      }
    }

    function showError(message) {
      const errorBox = document.getElementById('console-auth-error');
      const errorMessage = document.getElementById('console-error-message');
      if (!errorBox || !errorMessage) {
        return;
      }
      errorMessage.textContent = message;
      errorBox.hidden = false;
      if (errorTimeout) {
        clearTimeout(errorTimeout);
      }
      errorTimeout = window.setTimeout(() => {
        errorBox.hidden = true;
        errorTimeout = null;
      }, 5000);
    }

    function setLoginLoading(loading) {
      const button = document.getElementById('console-login-btn');
      if (!button) {
        return;
      }
      const icon = button.querySelector('.btn-icon');
      const text = button.querySelector('.btn-text');
      button.disabled = loading;
      if (icon) {
        icon.textContent = loading ? '⏳' : '🔓';
      }
      if (text) {
        text.textContent = loading
          ? uiText('auth_verify_loading', 'Verifying...')
          : uiText('auth_verify', 'Verify');
      }
    }

    function resetLoginButton() {
      setLoginLoading(false);
    }

    function resolveReturnTarget() {
      const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (!active) {
        return document.getElementById('console-session-trigger');
      }
      if (active.closest('#console-session-panel')) {
        return document.getElementById('console-session-trigger');
      }
      return active;
    }

    function openAuthModal(targetHref = null) {
      const modal = document.getElementById('console-auth-modal');
      if (!modal) {
        return;
      }
      lastTrigger = resolveReturnTarget();
      pendingTarget = targetHref;
      modal.hidden = false;
      modalOpen = true;
      document.body.style.overflow = 'hidden';
      hideError();
      closePanel();
      window.setTimeout(() => {
        const input = document.getElementById('console-token-input');
        if (input) {
          input.focus();
        }
      }, 40);
    }

    function closeAuthModal(clearTarget = true) {
      const modal = document.getElementById('console-auth-modal');
      const input = document.getElementById('console-token-input');
      const toggle = document.getElementById('console-token-toggle');
      const toggleIcon = toggle?.querySelector('span');
      if (!modal) {
        return;
      }
      modal.hidden = true;
      modalOpen = false;
      document.body.style.overflow = '';
      if (clearTarget) {
        pendingTarget = null;
      }
      if (input) {
        input.value = '';
        input.type = 'password';
      }
      if (toggleIcon) {
        toggleIcon.textContent = '👁️';
      }
      if (toggle) {
        toggle.setAttribute('aria-label', uiText('toggle_password_visibility', 'Toggle password visibility'));
      }
      hideError();
      resetLoginButton();
      if (lastTrigger && typeof lastTrigger.focus === 'function' && document.contains(lastTrigger)) {
        window.setTimeout(() => {
          if (document.contains(lastTrigger)) {
            lastTrigger.focus();
          }
        }, 0);
      }
    }

    async function refreshCurrentUser() {
      const response = await fetch('/api/auth/me');
      if (!response.ok) {
        throw new Error('auth probe failed');
      }
      const payload = await response.json();
      currentUser = payload.authenticated ? payload : null;
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

    async function handleLogin() {
      const input = document.getElementById('console-token-input');
      if (!input) {
        return;
      }
      const token = input.value.trim();
      const validationError = validateToken(token);
      if (validationError) {
        showError(validationError);
        return;
      }
      hideError();
      setLoginLoading(true);
      try {
        const response = await fetch(`/api/auth/login?lang=${encodeURIComponent(currentPageLanguage())}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        let payload;
        try {
          payload = await response.json();
        } catch (_error) {
          throw new Error(uiText('auth_bad_server_data', 'The server returned invalid data'));
        }
        if (!response.ok || payload.success !== true) {
          showError(payload.error || uiText('auth_verify_failed', 'Verification failed, please check your token'));
          return;
        }
        saveLocalSession();
        await refreshCurrentUser();
        const nextTarget = pendingTarget;
        closeAuthModal(false);
        pendingTarget = null;
        if (window.toast) {
          toast.success(uiText('auth_session_active', 'Session active'));
        }
        if (nextTarget) {
          window.location.href = nextTarget;
        }
      } catch (error) {
        showError(error.message || uiText('auth_network_error', 'Network error, please check your connection and try again'));
      } finally {
        setLoginLoading(false);
      }
    }

    async function handleLogout() {
      clearLocalSession();
      await requestSessionCleanup('Console logout request failed:');
      currentUser = null;
      renderSessionState();
      closePanel();
      window.location.href = sessionConfig.homeHref || '/';
    }

    function togglePasswordVisibility() {
      const input = document.getElementById('console-token-input');
      const toggle = document.getElementById('console-token-toggle');
      const icon = toggle?.querySelector('span');
      if (!input || !toggle) {
        return;
      }
      const revealing = input.type === 'password';
      input.type = revealing ? 'text' : 'password';
      if (icon) {
        icon.textContent = revealing ? '🙈' : '👁️';
      }
      toggle.setAttribute(
        'aria-label',
        revealing ? uiText('hide_password', 'Hide password') : uiText('show_password', 'Show password')
      );
    }

    function handleDocumentClick(event) {
      const trigger = document.getElementById('console-session-trigger');
      const panel = document.getElementById('console-session-panel');
      if (panelOpen && trigger && panel && !trigger.contains(event.target) && !panel.contains(event.target)) {
        closePanel();
      }
      if (modalOpen && event.target instanceof HTMLElement && event.target.id === 'console-auth-modal-backdrop') {
        closeAuthModal();
      }
    }

    function handleKeyDown(event) {
      if (event.key !== 'Escape') {
        return;
      }
      if (modalOpen) {
        closeAuthModal();
        return;
      }
      if (panelOpen) {
        closePanel();
      }
    }

    function bindEvents() {
      document.getElementById('console-session-trigger')?.addEventListener('click', togglePanel);
      document.getElementById('console-open-auth-modal-btn')?.addEventListener('click', () => openAuthModal());
      document.getElementById('console-logout-btn')?.addEventListener('click', handleLogout);
      document.getElementById('console-auth-modal-close')?.addEventListener('click', () => closeAuthModal());
      document.getElementById('console-cancel-auth-btn')?.addEventListener('click', () => closeAuthModal());
      document.getElementById('console-login-btn')?.addEventListener('click', handleLogin);
      document.getElementById('console-token-toggle')?.addEventListener('click', togglePasswordVisibility);
      document.getElementById('console-token-input')?.addEventListener('input', hideError);
      document.getElementById('console-token-input')?.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
          handleLogin();
        }
      });
      document.addEventListener('click', handleDocumentClick);
      document.addEventListener('keydown', handleKeyDown);
    }

    async function init() {
      renderSessionState();
      bindEvents();
      await initAuthState();
    }

    window.openAuthModal = openAuthModal;
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
