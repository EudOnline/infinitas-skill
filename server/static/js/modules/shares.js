import { apiPost, copyToClipboard } from './api.js';
import { uiText } from './config.js';

function initSharesPage() {
  const rows = document.querySelectorAll('table tbody tr');
  if (rows.length === 0) return;
  rows.forEach((row) => {
    const idCell = row.querySelector('td[data-label="ID"]');
    if (!idCell) return;
    idCell.title = uiText('copy_share_id', 'Click to copy ID');
    idCell.style.cursor = 'copy';
    idCell.addEventListener('click', async () => {
      await copyToClipboard(idCell.textContent.trim());
    });
  });

  document.body.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-action="revoke-share-link"]');
    if (!button) return;
    button.disabled = true;
    try {
      await apiPost(`/api/library/share-links/${encodeURIComponent(button.dataset.grantId)}/revoke`, {});
      window.location.reload();
    } catch (error) {
      button.disabled = false;
      window.toast?.error?.(error.message || uiText('share_revoke_error', 'Failed to revoke share link'));
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSharesPage);
} else {
  initSharesPage();
}

export { initSharesPage };
