import { initCardSwipe } from './card-swipe.js';
import { apiPost } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelector('[data-manage-tabs]');
  if (!tabs) return;

  tabs.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-view]');
    if (!btn) return;
    tabs.querySelectorAll('[data-view]').forEach((b) => {
      const isActive = b === btn;
      b.classList.toggle('is-active', isActive);
      b.setAttribute('aria-selected', String(isActive));
    });
    document.querySelectorAll('[data-view-panel]').forEach((panel) => {
      panel.classList.toggle('hidden', panel.dataset.viewPanel !== btn.dataset.view);
    });
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
    btn.disabled = true;
    btn.textContent = '...';
    try {
      await apiPost(`/api/library/tokens/${credId}/revoke`);
      const card = btn.closest('article');
      if (card) {
        card.style.transition = 'opacity 0.3s';
        card.style.opacity = '0';
        setTimeout(() => card.remove(), 300);
      } else {
        const row = btn.closest('tr');
        if (row) row.remove();
      }
    } catch {
      btn.disabled = false;
      btn.textContent = btn.dataset.label || 'Revoke';
    }
  });

  // Card swipe for mobile token cards
  initCardSwipe('[data-view-panel="tokens"]');
});
