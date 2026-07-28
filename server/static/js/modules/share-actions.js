import { apiPost } from './api.js';
import { uiText } from './config.js';
import { getSharedToast } from './toast.js';

let initialized = false;

async function revokeShareLink(button) {
  const grantId = button.dataset.grantId;
  if (!grantId) return;
  const confirmed = confirm(uiText(
    'confirm_revoke_share_link',
    'Are you sure you want to revoke this share link? This action cannot be undone.',
  ));
  if (!confirmed) return;

  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = '...';
  try {
    await apiPost(`/api/v1/share-links/${grantId}/revoke`);
    const container = button.closest('article, tr');
    if (container) container.remove();
    getSharedToast()?.success(uiText('share_revoked', 'Share link revoked'));
  } catch (error) {
    getSharedToast()?.error(error.message || uiText('share_revoke_error', 'Revoke failed'));
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function initShareRevocation() {
  if (initialized) return;
  initialized = true;
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-action="revoke-share-link"]');
    if (button) void revokeShareLink(button);
  });
}

export { initShareRevocation };
