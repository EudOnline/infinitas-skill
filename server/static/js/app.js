/**
 * infinitas-skill v2 - Core JavaScript (ES module orchestrator)
 */
import { ToastManager } from './modules/toast.js';
import { ThemeManager, setToastRef as setThemeToastRef } from './modules/theme.js';
import { SearchManager, setSearchToastRef } from './modules/search.js';
import { bindCopyTriggers, drainPendingToasts, setApiToastRef } from './modules/api.js';
import { initSortableTable, initFilterableTable } from './modules/table-interactions.js';

// Create shared instances
const toast = new ToastManager();
const themeManager = new ThemeManager();

// Wire toast references into all modules
setThemeToastRef(toast);
setSearchToastRef(toast);
setApiToastRef(toast);

// Focus mode toggle
(function initFocusMode() {
  const STORAGE_KEY = 'infinitas-focus-mode';
  const root = document.documentElement;
  let saved = null;
  try { saved = localStorage.getItem(STORAGE_KEY); } catch (_) {}
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
      try { localStorage.setItem(STORAGE_KEY, String(active)); } catch (_) {}
      btn.setAttribute('aria-pressed', String(active));
    });
  });
})();

// Main initialization
document.addEventListener('DOMContentLoaded', () => {
  // Scroll nav to active item on mobile
  const nav = document.querySelector('.nav');
  const active = nav && nav.querySelector('a[aria-current="page"]');
  if (nav && active) {
    const navRect = nav.getBoundingClientRect();
    const activeRect = active.getBoundingClientRect();
    const scrollLeft = activeRect.left - navRect.left - (navRect.width / 2) + (activeRect.width / 2);
    nav.scrollLeft = Math.max(0, scrollLeft + nav.scrollLeft);
  }

  bindCopyTriggers();
  drainPendingToasts();

  // Initialize search
  try {
    new SearchManager();
  } catch (err) {
    console.error('Failed to initialize search:', err);
  }

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
        el.classList.add('reveal-pending');
        const delay = getComputedStyle(el).getPropertyValue('--reveal-index');
        if (delay) {
          el.style.transitionDelay = `${parseInt(delay, 10) * 100}ms`;
        }
      });

      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.remove('reveal-pending');
            entry.target.classList.add('reveal-visible');
            observer.unobserve(entry.target);
          }
        });
      }, {
        threshold: 0.1,
        rootMargin: '0px 0px -10% 0px'
      });

      revealElements.forEach(el => observer.observe(el));
    }
  }
});
