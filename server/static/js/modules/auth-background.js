import { getCsrfToken, logError, uiText } from './config.js';

const BG_STORAGE_KEY = 'infinitas_bg_settings';

export class AuthBackgroundController {
  constructor({ presets, isLoggedIn, isPanelOpen }) {
    this.presets = presets;
    this.isLoggedIn = isLoggedIn;
    this.isPanelOpen = isPanelOpen;
    this.observer = null;
  }

  getSettings() {
    try {
      const saved = window.localStorage.getItem(BG_STORAGE_KEY);
      return saved ? JSON.parse(saved) : { light: null, dark: null };
    } catch (error) {
      logError('Failed to parse background settings:', error);
      return { light: null, dark: null };
    }
  }

  setCurrentBgId(theme, bgId) {
    const settings = this.getSettings();
    settings[theme] = bgId;
    try {
      window.localStorage.setItem(BG_STORAGE_KEY, JSON.stringify(settings));
    } catch (_error) {
      // Local preferences remain optional when storage is unavailable.
    }
  }

  currentBgId(theme) {
    return this.getSettings()[theme] || null;
  }

  apply(theme, bgId) {
    const preset = (this.presets[theme] || []).find((item) => item.id === bgId);
    const variableName = theme === 'dark' ? '--bg-image-dark' : '--bg-image';
    if (!preset?.url) {
      document.body.style.removeProperty(variableName);
      return;
    }
    const property = theme === 'light' ? '--bg-gradient-light' : '--bg-gradient-dark';
    const gradient = getComputedStyle(document.body).getPropertyValue(property).trim();
    const safeUrl = preset.url.replace(/['()\\]/g, '\\$&');
    document.body.style.setProperty(variableName, `${gradient}, url('${safeUrl}')`);
  }

  renderSelector(theme) {
    const grid = document.getElementById('bg-grid');
    const themeLabel = document.getElementById('bg-theme-label');
    if (!grid) return;
    const currentBgId = this.currentBgId(theme);
    if (themeLabel) {
      themeLabel.textContent = theme === 'light'
        ? uiText('user_panel_theme_light', '浅色')
        : uiText('user_panel_theme_dark', '深色');
    }
    grid.replaceChildren(...(this.presets[theme] || []).map((preset) => {
      const button = document.createElement('button');
      const isActive = preset.id === currentBgId;
      button.className = `bg-option ${preset.url ? '' : 'bg-option--gradient'} ${isActive ? 'is-active' : ''}`;
      button.dataset.bgId = preset.id;
      button.dataset.name = preset.name;
      button.type = 'button';
      button.setAttribute('aria-label', preset.name);
      button.setAttribute('aria-pressed', String(isActive));
      if (preset.url) {
        const safeUrl = preset.url.replace(/['()\\]/g, '\\$&');
        button.style.backgroundImage = `url('${safeUrl}')`;
      }
      return button;
    }));
    if (grid.dataset.delegateBound) return;
    grid.dataset.delegateBound = 'true';
    grid.addEventListener('click', (event) => {
      const button = event.target.closest('.bg-option');
      if (button) this.select(this.currentTheme(), button.dataset.bgId);
    });
  }

  currentTheme() {
    return document.documentElement.getAttribute('data-color-scheme') || 'light';
  }

  async select(theme, bgId) {
    this.apply(theme, bgId);
    this.setCurrentBgId(theme, bgId);
    if (this.isLoggedIn()) await this.saveRemote(theme, bgId);
    const grid = document.getElementById('bg-grid');
    grid?.querySelectorAll('.bg-option').forEach((button) => {
      const isActive = button.dataset.bgId === bgId;
      button.classList.toggle('is-active', isActive);
      button.setAttribute('aria-pressed', String(isActive));
    });
  }

  async saveRemote(theme, bgId) {
    try {
      const response = await fetch('/api/v1/background/set', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ theme, bg_id: bgId }),
      });
      if (!response.ok) logError('Failed to save background to server');
    } catch (error) {
      logError('Network error saving background:', error);
    }
  }

  async loadRemote() {
    try {
      const response = await fetch('/api/v1/background/me', { credentials: 'same-origin' });
      if (!response.ok) return;
      const payload = await response.json();
      for (const theme of ['light', 'dark']) {
        const bgId = payload[`${theme}_bg_id`];
        if (!bgId) continue;
        this.setCurrentBgId(theme, bgId);
        if (this.currentTheme() === theme) this.apply(theme, bgId);
      }
    } catch (error) {
      logError('Failed to fetch background:', error);
    }
  }

  init() {
    const theme = this.currentTheme();
    this.apply(theme, this.currentBgId(theme));
    this.observer = new MutationObserver((mutations) => {
      if (!mutations.some((mutation) => mutation.attributeName === 'data-color-scheme')) return;
      const nextTheme = this.currentTheme();
      this.apply(nextTheme, this.currentBgId(nextTheme));
      if (this.isPanelOpen()) this.renderSelector(nextTheme);
    });
    this.observer.observe(document.documentElement, { attributes: true });
    window.addEventListener('beforeunload', () => this.observer?.disconnect());
  }
}
