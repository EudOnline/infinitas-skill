/**
 * infinitas-skill v2 - Core JavaScript (ES module orchestrator)
 */
import { infinitasAppShell, APP_UI, APP_SESSION, AUTH_SESSION_CONFIG } from './modules/config.js';
import { ToastManager } from './modules/toast.js';
import { ThemeManager, setToastRef as setThemeToastRef } from './modules/theme.js';
import { SearchManager, setSearchToastRef } from './modules/search.js';
import { copyToClipboard, bindCopyTriggers, apiGet, apiPost, apiPatch, drainPendingToasts, setApiToastRef } from './modules/api.js';
import { initSortableTable, initFilterableTable } from './modules/table-interactions.js';
import {
  initDelegatedActions,
  initCreateSkill,
  initCreateDraft,
  initDraftDetail,
  initReleaseDetail,
  initShareDetail,
  initAccessTokens,
  setLifecycleToastRef,
} from './modules/lifecycle.js';

// Create shared instances
const toast = new ToastManager();
const themeManager = new ThemeManager();

// Wire toast references into all modules
setThemeToastRef(toast);
setSearchToastRef(toast);
setApiToastRef(toast);
setLifecycleToastRef(toast);

// Legacy globals (backward compat for auth-session.js and inline references)
window.APP_UI = APP_UI;
window.APP_SESSION = APP_SESSION;
window.AUTH_SESSION_CONFIG = AUTH_SESSION_CONFIG;
window.infinitasAppShell = infinitasAppShell;
window.toast = toast;
window.themeManager = themeManager;

// Focus mode toggle
(function initFocusMode() {
  const STORAGE_KEY = 'infinitas-focus-mode';
  const root = document.documentElement;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'true') {
    root.classList.add('focus-mode');
  }

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('focus-mode-toggle');
    if (!btn) return;
    if (root.classList.contains('focus-mode')) {
      btn.setAttribute('aria-pressed', 'true');
    }
    btn.addEventListener('click', () => {
      const active = root.classList.toggle('focus-mode');
      localStorage.setItem(STORAGE_KEY, String(active));
      btn.setAttribute('aria-pressed', String(active));
    });
  });
})();

// Main initialization
document.addEventListener('DOMContentLoaded', () => {
  bindCopyTriggers();
  drainPendingToasts();

  // Initialize search
  try {
    window.searchManager = new SearchManager();
  } catch (err) {
    console.error('Failed to initialize search:', err);
  }

  // Initialize lifecycle action pages
  initDelegatedActions();
  initCreateSkill();
  initCreateDraft();
  initDraftDetail();
  initReleaseDetail();
  initShareDetail();
  initAccessTokens();

  // Initialize table sort and filter on all tables
  document.querySelectorAll('table').forEach((table) => {
    initSortableTable(table);
    const filterInput = table.closest('section')?.querySelector('[data-table-filter]');
    if (filterInput) {
      initFilterableTable(table, filterInput);
    }
  });

  // Animate elements on scroll using Intersection Observer
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  if (!prefersReducedMotion.matches && 'IntersectionObserver' in window) {
    const revealElements = document.querySelectorAll('[data-reveal]');

    if (revealElements.length > 0) {
      revealElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(14px)';
        el.style.transition = `opacity 520ms var(--ease-out-gentle), transform 520ms var(--ease-out-gentle)`;
        const delay = getComputedStyle(el).getPropertyValue('--reveal-index');
        if (delay) {
          el.style.transitionDelay = `${parseInt(delay, 10) * 100}ms`;
        }
      });

      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            observer.unobserve(entry.target);
          }
        });
      }, {
        threshold: 0.1,
        rootMargin: '0px 0px -10% 0px'
      });

      revealElements.forEach(el => observer.observe(el));
      window._revealObserver = observer;
    }
  }
});
