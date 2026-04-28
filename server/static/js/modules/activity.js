function initActivityPage() {
  const filterGroup = document.querySelector('[data-activity-filter]');
  const list = document.querySelector('[data-activity-list]');
  if (!filterGroup || !list) return;
  const items = Array.from(list.querySelectorAll('[data-event-type]'));
  if (items.length === 0) return;

  const applyFilter = (value) => {
    items.forEach((item) => {
      const visible = value === 'all' || item.dataset.eventType === value;
      item.hidden = !visible;
    });
  };

  filterGroup.querySelectorAll('[data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      const value = button.dataset.filter || 'all';
      filterGroup.querySelectorAll('[data-filter]').forEach((item) => {
        const active = item === button;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-pressed', String(active));
      });
      applyFilter(value);
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initActivityPage);
} else {
  initActivityPage();
}

export { initActivityPage };
