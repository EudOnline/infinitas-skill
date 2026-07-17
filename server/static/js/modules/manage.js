import { initCardSwipe } from './card-swipe.js';
import { apiPost } from './api.js';
import { uiText } from './config.js';
import { getSharedToast } from './toast.js';

document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelector('[data-manage-tabs]');
  if (!tabs) return;

  function activateTab(btn) {
    tabs.querySelectorAll('[data-view]').forEach((b) => {
      const isActive = b === btn;
      b.classList.toggle('is-active', isActive);
      b.setAttribute('aria-selected', String(isActive));
      b.setAttribute('tabindex', isActive ? '0' : '-1');
    });
    document.querySelectorAll('[data-view-panel]').forEach((panel) => {
      panel.classList.toggle('hidden', panel.dataset.viewPanel !== btn.dataset.view);
    });
    btn.focus();
  }

  tabs.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-view]');
    if (!btn) return;
    activateTab(btn);
  });

  function activateHashTab() {
    const view = window.location.hash.slice(1);
    if (!view) return;
    const button = tabs.querySelector(`[data-view="${CSS.escape(view)}"]`);
    if (button) activateTab(button);
  }

  activateHashTab();
  window.addEventListener('hashchange', activateHashTab);

  // WAI-ARIA Tabs keyboard navigation
  tabs.addEventListener('keydown', (e) => {
    const btn = e.target.closest('[data-view]');
    if (!btn) return;
    const allTabs = Array.from(tabs.querySelectorAll('[data-view]'));
    const idx = allTabs.indexOf(btn);
    let next = -1;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      next = (idx + 1) % allTabs.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      next = (idx - 1 + allTabs.length) % allTabs.length;
    } else if (e.key === 'Home') {
      e.preventDefault();
      next = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      next = allTabs.length - 1;
    }
    if (next >= 0) {
      activateTab(allTabs[next]);
    }
  });

  // Library filtering
  const filterGroup = document.querySelector('[data-manage-filter]');
  const searchInput = document.querySelector('[data-manage-search]');

  function filterCards(kind, query) {
    document.querySelectorAll('[data-kind]').forEach((card) => {
      const kindMatch = kind === 'all' || card.dataset.kind === kind;
      const textMatch = !query || card.dataset.name.includes(query) || card.dataset.summary.includes(query);
      card.style.display = (kindMatch && textMatch) ? '' : 'none';
    });
  }

  if (filterGroup) {
    filterGroup.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-filter]');
      if (!btn) return;
      filterGroup.querySelectorAll('[data-filter]').forEach((b) => {
        const isActive = b === btn;
        b.classList.toggle('is-active', isActive);
        b.setAttribute('aria-pressed', String(isActive));
      });
      filterCards(btn.dataset.filter, searchInput?.value.toLowerCase() || '');
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const active = filterGroup?.querySelector('.is-active');
      filterCards(active?.dataset.filter || 'all', searchInput.value.toLowerCase());
    });
  }

  // Revoke token handler
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action="revoke-token"]');
    if (!btn) return;
    const credId = btn.dataset.credentialId;
    if (!credId) return;
    if (!confirm(uiText('confirm_revoke_token', 'Are you sure you want to revoke this token? This action cannot be undone.'))) {
      return;
    }
    btn.disabled = true;
    btn.textContent = '...';
    try {
      await apiPost(`/api/v1/object-tokens/tokens/${credId}/revoke`);
      const card = btn.closest('article');
      if (card) {
        card.style.transition = 'opacity 0.3s';
        card.style.opacity = '0';
        setTimeout(() => card.remove(), 300);
      } else {
        const row = btn.closest('tr');
        if (row) row.remove();
      }
    } catch (err) {
      getSharedToast()?.error(err.message || 'Revoke failed');
      btn.disabled = false;
      btn.textContent = btn.dataset.label || 'Revoke';
    }
  });

  // Revoke share-link handler
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action="revoke-share-link"]');
    if (!btn) return;
    const grantId = btn.dataset.grantId;
    if (!grantId) return;
    if (!confirm(uiText('confirm_revoke_share_link', 'Are you sure you want to revoke this share link? This action cannot be undone.'))) {
      return;
    }
    btn.disabled = true;
    btn.textContent = '...';
    try {
      await apiPost(`/api/v1/share-links/${grantId}/revoke`);
      const card = btn.closest('article');
      if (card) {
        card.style.transition = 'opacity 0.3s';
        card.style.opacity = '0';
        setTimeout(() => card.remove(), 300);
      } else {
        const row = btn.closest('tr');
        if (row) row.remove();
      }
    } catch (err) {
      getSharedToast()?.error(err.message || 'Revoke failed');
      btn.disabled = false;
      btn.textContent = btn.dataset.label || 'Revoke';
    }
  });

  // Card swipe for mobile token cards
  initCardSwipe('[data-view-panel="tokens"]');
});
