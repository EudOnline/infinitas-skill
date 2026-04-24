/**
 * Home-page authentication session manager.
 *
 * Handles the user trigger icon, user panel (login / logged-in state),
 * background manager, protected-link interception, and the login modal
 * lifecycle for the home page.
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
// Background settings storage key
// ---------------------------------------------------------------------------

const BG_STORAGE_KEY = 'infinitas_bg_settings';

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function initHomeAuthSession() {
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
  const suppressInitialModal = homeConfig.suppressInitialModal === true;
  let currentUser = initialSessionUser();
  let isUserPanelOpen = false;
  let bgObserver = null;

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

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

  // -----------------------------------------------------------------------
  // BackgroundManager
  // -----------------------------------------------------------------------

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

  // -----------------------------------------------------------------------
  // UI helpers
  // -----------------------------------------------------------------------

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
    panel.classList.remove('user-panel--flip');
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
    panel.classList.remove('user-panel--flip');
    trigger.setAttribute('aria-expanded', String(isUserPanelOpen));
    if (isUserPanelOpen && currentUser) {
      const theme = document.documentElement.getAttribute('data-color-scheme') || 'light';
      BackgroundManager.renderSelector(theme);
    }
    if (isUserPanelOpen) {
      // 视口边界检测：若面板超出视口则自动翻转展开方向
      requestAnimationFrame(() => {
        const rect = panel.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const isMobile = window.innerWidth <= 767;
        const margin = 12;
        if (!isMobile && rect.bottom > viewportHeight - margin) {
          panel.classList.add('user-panel--flip');
        } else if (isMobile && rect.top < margin) {
          panel.classList.add('user-panel--flip');
        }
      });
    }
  }

  // -----------------------------------------------------------------------
  // Auth state management
  // -----------------------------------------------------------------------

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

  // -----------------------------------------------------------------------
  // Event handlers
  // -----------------------------------------------------------------------

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

  // -----------------------------------------------------------------------
  // Modal controller
  // -----------------------------------------------------------------------

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
        window.location.href = AUTH_SESSION_CONFIG.homeHref || '/';
      }
    },
  });

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------

  async function init() {
    BackgroundManager.init();
    updateUserTriggerIcon(!!currentUser);
    updateUserPanelState();
    await initAuthState();
    if (standaloneLoginPage && currentUser) {
      window.location.replace(AUTH_SESSION_CONFIG.homeHref || '/');
      return;
    }
    bindEvents();
    const homeAuthModalStartsVisible = !standaloneLoginPage && controller.dom.modal && !controller.dom.modal.hidden;
    if (homeAuthModalStartsVisible) {
      if (suppressInitialModal && !currentUser) {
        controller.dom.modal.hidden = true;
      } else {
        openAuthModal();
      }
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
