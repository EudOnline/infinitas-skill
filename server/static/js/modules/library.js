import { uiText } from './config.js';

function initLibraryFilters() {
  const group = document.querySelector('[data-library-filter]');
  const searchInput = document.querySelector('[data-library-search]');
  const cards = Array.from(document.querySelectorAll('.object-card'));
  const emptyState = document.getElementById('library-empty-state');
  if (!group || !searchInput || cards.length === 0) return;

  let activeFilter = 'all';

  const applyFilters = () => {
    const query = String(searchInput.value || '').trim().toLowerCase();
    let visibleCount = 0;

    cards.forEach((card) => {
      const kind = card.dataset.kind || '';
      const haystack = `${card.dataset.name || ''} ${card.dataset.summary || ''}`.trim();
      const matchesFilter = activeFilter === 'all' || kind === activeFilter;
      const matchesQuery = !query || haystack.includes(query);
      const visible = matchesFilter && matchesQuery;
      card.hidden = !visible;
      if (visible) visibleCount += 1;
    });

    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  };

  group.querySelectorAll('[data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      activeFilter = button.dataset.filter || 'all';
      group.querySelectorAll('[data-filter]').forEach((item) => {
        const active = item === button;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-pressed', String(active));
      });
      applyFilters();
    });
  });

  searchInput.addEventListener('input', applyFilters);
  applyFilters();
}

function initObjectTabs() {
  const tabs = Array.from(document.querySelectorAll('[role="tab"][aria-controls]'));
  if (tabs.length === 0) return;

  const activateTab = (tab) => {
    const targetId = tab.getAttribute('aria-controls');
    tabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-selected', String(active));
      const panel = document.getElementById(item.getAttribute('aria-controls'));
      if (panel) {
        panel.hidden = !active;
        panel.classList.toggle('hidden', !active);
      }
    });
    if (targetId) {
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${targetId.replace('-panel', '')}`);
    }
  };

  tabs.forEach((tab) => {
    tab.addEventListener('click', (event) => {
      event.preventDefault();
      activateTab(tab);
    });
  });

  const requested = window.location.hash.replace(/^#/, '');
  const requestedTab = tabs.find((tab) => {
    const panelId = tab.getAttribute('aria-controls') || '';
    return panelId === `${requested}-panel`;
  });
  activateTab(requestedTab || tabs[0]);
}

function initLibraryPage() {
  initLibraryFilters();
  initObjectTabs();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLibraryPage);
} else {
  initLibraryPage();
}

export { initLibraryPage };
