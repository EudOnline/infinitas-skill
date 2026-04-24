/**
 * Auth session initialization (ES module thin wrapper)
 */
import { initHomeAuthSession, setToastRef as setHomeToastRef } from './modules/auth-home.js';
import { initConsoleAuthSession, setToastRef as setConsoleToastRef } from './modules/auth-console.js';

function initAll() {
  // Wait for app.js globals to be available
  const toast = window.toast || null;
  setHomeToastRef(toast);
  setConsoleToastRef(toast);

  initHomeAuthSession();
  initConsoleAuthSession();

  // Listen for auth-required events from search module
  document.addEventListener('infinitas:auth-required', () => {
    if (typeof window.openConsoleAuthModal === 'function') {
      window.openConsoleAuthModal();
    } else if (typeof window.openHomeAuthModal === 'function') {
      window.openHomeAuthModal();
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAll);
} else {
  initAll();
}
