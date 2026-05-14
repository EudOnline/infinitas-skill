document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelector('[data-manage-tabs]');
  if (!tabs) return;

  tabs.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-view]');
    if (!btn) return;
    tabs.querySelectorAll('[data-view]').forEach((b) => {
      b.classList.toggle('is-active', b === btn);
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
      filterGroup.querySelectorAll('[data-filter]').forEach((b) => b.classList.toggle('is-active', b === btn));
      filterCards(btn.dataset.filter, searchInput?.value.toLowerCase() || '');
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const active = filterGroup?.querySelector('.is-active');
      filterCards(active?.dataset.filter || 'all', searchInput.value.toLowerCase());
    });
  }
});
