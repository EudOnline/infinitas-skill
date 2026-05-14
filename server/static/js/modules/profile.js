import { apiGet } from './api.js';
import { uiText } from './config.js';

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-profile-tabs]');
  if (!root) return;

  // Tab switching
  root.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-tab]');
    if (!btn) return;

    root.querySelectorAll('[data-tab]').forEach((b) => {
      b.classList.toggle('is-active', b === btn);
      b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
    });

    document.querySelectorAll('[data-tab-panel]').forEach((panel) => {
      panel.classList.toggle('hidden', panel.dataset.tabPanel !== btn.dataset.tab);
    });
  });

  // Load profile data from API
  try {
    const data = await apiGet('/api/v1/profile/me');
    if (!data) return;

    // Update identity card
    const scopes = data.identity?.scopes?.join(', ') || '-';
    const expiry = data.identity?.expires_at
      ? new Date(data.identity.expires_at).toLocaleDateString()
      : '-';

    const scopesEl = document.getElementById('profile-scopes');
    const expiryEl = document.getElementById('profile-token-expiry');
    if (scopesEl) scopesEl.textContent = `${uiText('profile_scopes', '权限')}: ${scopes}`;
    if (expiryEl) expiryEl.textContent = `${uiText('profile_token_expiry', 'Token 有效期')}: ${expiry}`;

    // Render skills
    const skillsList = document.getElementById('profile-skills-list');
    if (skillsList && data.accessible_skills?.length) {
      skillsList.innerHTML = data.accessible_skills
        .map((s) => `
          <article class="kawaii-card animate-in">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="font-display text-sm font-bold text-kawaii-ink">${s.display_name}</h3>
                <p class="text-xs text-kawaii-ink-muted">${s.slug} · ${s.kind}</p>
              </div>
              <span class="kawaii-badge kawaii-badge--success">active</span>
            </div>
          </article>`)
        .join('');
    } else if (skillsList) {
      skillsList.innerHTML = `
        <div class="kawaii-card animate-in text-center py-8 text-kawaii-ink-muted text-sm">
          ${uiText('profile_no_skills', '暂无可访问技能')}
        </div>`;
    }

    // Render history
    const historyList = document.getElementById('profile-history-list');
    if (historyList && data.operation_history?.length) {
      historyList.innerHTML = data.operation_history
        .map((e) => `
          <article class="kawaii-card animate-in">
            <div class="flex items-center gap-2">
              <span class="text-xs text-kawaii-ink-muted">${new Date(e.occurred_at).toLocaleString()}</span>
              <span class="kawaii-badge kawaii-badge--soft">${e.event_type}</span>
            </div>
          </article>`)
        .join('');
    }

    // Render policy
    const policyList = document.getElementById('profile-policy-list');
    if (policyList && data.policy && Object.keys(data.policy).length) {
      policyList.innerHTML = `
        <article class="kawaii-card animate-in">
          <pre class="text-xs text-kawaii-ink-soft overflow-x-auto">${JSON.stringify(data.policy, null, 2)}</pre>
        </article>`;
    }
  } catch (err) {
    console.error('Failed to load profile:', err);
  }
});
