/**
 * Client-side table sort and filter interactions
 */

export function initSortableTable(tableEl) {
  const headers = tableEl.querySelectorAll('th[data-sort]');
  if (!headers.length) return;

  headers.forEach((th) => {
    th.style.cursor = 'pointer';
    th.style.userSelect = 'none';

    const sortType = th.dataset.sort;
    const indicator = document.createElement('span');
    indicator.className = 'sort-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    indicator.textContent = ' ↕';
    th.appendChild(indicator);

    th.addEventListener('click', () => {
      const currentDir = th.dataset.sortDir || '';
      const newDir = currentDir === 'asc' ? 'desc' : 'asc';

      headers.forEach((h) => {
        h.dataset.sortDir = '';
        const ind = h.querySelector('.sort-indicator');
        if (ind) ind.textContent = ' ↕';
      });

      th.dataset.sortDir = newDir;
      indicator.textContent = newDir === 'asc' ? ' ↑' : ' ↓';

      sortTable(tableEl, th.cellIndex, sortType, newDir);
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
