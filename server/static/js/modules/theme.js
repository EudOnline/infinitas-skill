/**
 * Theme manager - light/dark mode toggle
 */
import { uiText, uiTemplate } from './config.js';

let toastRef = null;

export function setToastRef(ref) {
  toastRef = ref;
}

export class ThemeManager {
  constructor() {
    const storageKey = 'kawaii-color-scheme';
    this.storageKey = storageKey;
    this.systemPreference = window.matchMedia('(prefers-color-scheme: dark)');
    this.current = this.resolveInitialScheme();
    this.init();
  }

  resolveInitialScheme() {
    const html = document.documentElement;
    const fromDom = html.dataset.colorScheme;
    if (fromDom === 'light' || fromDom === 'dark') {
      return fromDom;
    }

    try {
      const stored = window.localStorage.getItem(this.storageKey);
      if (stored === 'light' || stored === 'dark') {
        return stored;
      }
    } catch (_err) {
      // Ignore storage access failures and fall back to system preference.
    }

    return this.systemPreference.matches ? 'dark' : 'light';
  }

  updateButtons(scheme) {
    document.querySelectorAll('[data-theme-choice]').forEach((button) => {
      const active = button.dataset.themeChoice === scheme;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  init() {
    this.apply(this.current, false);
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-theme-choice]');
      if (btn) {
        this.set(btn.dataset.themeChoice);
      }
    });
    const settingsToggle = document.getElementById('mobile-settings-toggle');
    const settingsPanel = document.getElementById('topbar-settings');
    if (settingsToggle && settingsPanel) {
      settingsToggle.addEventListener('click', () => {
        const open = settingsPanel.classList.toggle('is-open');
        settingsToggle.setAttribute('aria-expanded', String(open));
      });
    }
  }

  apply(scheme, save = true) {
    const html = document.documentElement;
    scheme = scheme === 'dark' ? 'dark' : 'light';
    html.dataset.colorScheme = scheme;
    this.updateButtons(scheme);
    this.current = scheme;

    if (save) {
      try {
        window.localStorage.setItem(this.storageKey, scheme);
      } catch (_err) {
        // Ignore storage failures so the toggle still works for the session.
      }
    }
  }

  toggle() {
    const currentScheme = document.documentElement.dataset.colorScheme === 'dark' ? 'dark' : 'light';
    const next = currentScheme === 'dark' ? 'light' : 'dark';
    this.apply(next);
    if (toastRef) {
      toastRef.success(uiTemplate('theme_switched', '已切换到 {theme}', { theme: this.getThemeName(next) }));
    }
  }

  set(scheme) {
    if (scheme === 'light' || scheme === 'dark') {
      this.apply(scheme);
    }
  }

  getThemeName(scheme) {
    const names = {
      light: uiText('theme_light_name', '浅色主题'),
      dark: uiText('theme_dark_name', '深色主题'),
    };
    return names[scheme] || scheme;
  }
}
