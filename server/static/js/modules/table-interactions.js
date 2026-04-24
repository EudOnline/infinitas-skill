/**
 * Client-side table sort and filter interactions
 */

export function initSortableTable(tableEl) {
  const headers = tableEl.querySelectorAll('th[data-sort]');
  if (!headers.length) return;

  // Ensure live region exists for sort announcements
  let liveRegion = document.getElementById('table-sort-live');
  if (!liveRegion) {
    liveRegion = document.createElement('div');
    liveRegion.id = 'table-sort-live';
    liveRegion.className = 'sr-only';
    liveRegion.setAttribute('aria-live', 'polite');
    liveRegion.setAttribute('aria-atomic', 'true');
    document.body.appendChild(liveRegion);
  }

  headers.forEach((th) => {
    th.style.cursor = 'pointer';
    th.style.userSelect = 'none';
    th.setAttribute('tabindex', '0');
    th.setAttribute('role', 'columnheader');
    th.setAttribute('scope', 'col');

    const sortType = th.dataset.sort;
    const indicator = document.createElement('span');
    indicator.className = 'sort-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    indicator.textContent = ' ↕';
    th.appendChild(indicator);

    function activateSort() {
      const currentDir = th.dataset.sortDir || '';
      const newDir = currentDir === 'asc' ? 'desc' : 'asc';

      headers.forEach((h) => {
        h.dataset.sortDir = '';
        h.removeAttribute('aria-sort');
        const ind = h.querySelector('.sort-indicator');
        if (ind) ind.textContent = ' ↕';
      });

      th.dataset.sortDir = newDir;
      th.setAttribute('aria-sort', newDir === 'asc' ? 'ascending' : 'descending');
      indicator.textContent = newDir === 'asc' ? ' ↑' : ' ↓';

      sortTable(tableEl, th.cellIndex, sortType, newDir);

      const label = th.textContent.replace(/[↑↓↕]/g, '').trim();
      const directionLabel = newDir === 'asc' ? '升序' : '降序';
      if (liveRegion) liveRegion.textContent = `${label}：已按${directionLabel}排序`;
    }

    th.addEventListener('click', activateSort);
    th.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activateSort();
      }
    });
  });
}

function sortTable(tableEl, colIndex, sortType, direction) {
  const tbody = tableEl.querySelector('tbody');
  if (!tbody) return;

  const rows = Array.from(tbody.querySelectorAll('tr'));
  const multiplier = direction === 'asc' ? 1 : -1;

  rows.sort((a, b) => {
    const aVal = (a.cells[colIndex]?.textContent || '').trim();
    const bVal = (b.cells[colIndex]?.textContent || '').trim();

    if (sortType === 'number') {
      return multiplier * (parseFloat(aVal) - parseFloat(bVal));
    }
    if (sortType === 'date') {
      const aTime = Date.parse(aVal);
      const bTime = Date.parse(bVal);
      if (isNaN(aTime) && isNaN(bTime)) return 0;
      if (isNaN(aTime)) return 1;
      if (isNaN(bTime)) return -1;
      return multiplier * (aTime - bTime);
    }
    return multiplier * aVal.localeCompare(bVal, undefined, { sensitivity: 'base' });
  });

  rows.forEach((row) => tbody.appendChild(row));
}

export function initFilterableTable(tableEl, inputEl) {
  if (!inputEl || !tableEl) return;

  const tbody = tableEl.querySelector('tbody');
  if (!tbody) return;

  inputEl.addEventListener('input', () => {
    const query = inputEl.value.toLowerCase().trim();
    const rows = tbody.querySelectorAll('tr');

    rows.forEach((row) => {
      if (!query) {
        row.hidden = false;
        return;
      }
      const text = (row.textContent || '').toLowerCase();
      row.hidden = !text.includes(query);
    });
  });
}
