/**
 * Auth session initialization (ES module)
 */
import { initHomeAuthSession } from './modules/auth-home.js';
import { initConsoleAuthSession, setToastRef as setConsoleToastRef } from './modules/auth-console.js';
import { getSharedToast } from './modules/toast.js';

function initAll() {
  const toast = getSharedToast();
  setConsoleToastRef(toast);

  initHomeAuthSession();
  initConsoleAuthSession();

  // Listen for auth-required events from search module
  document.addEventListener('infinitas:auth-required', () => {
    document.dispatchEvent(new CustomEvent('infinitas:open-auth-modal'));
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAll);
} else {
  initAll();
}
