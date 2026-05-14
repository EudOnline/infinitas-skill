import { apiGet } from './api.js';
import { uiText } from './config.js';

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function createSkillCard(s) {
  const article = document.createElement('article');
  article.className = 'kawaii-card animate-in';
  article.innerHTML = `
    <div class="flex items-center justify-between">
      <div>
        <h3 class="font-display text-sm font-bold text-kawaii-ink"></h3>
        <p class="text-xs text-kawaii-ink-muted"></p>
      </div>
      <span class="kawaii-badge kawaii-badge--success">active</span>
    </div>`;
  article.querySelector('h3').textContent = s.display_name;
  article.querySelector('p').textContent = `${s.slug} · ${s.kind}`;
  return article;
}

function createHistoryCard(e) {
  const article = document.createElement('article');
  article.className = 'kawaii-card animate-in';
  article.innerHTML = `
    <div class="flex items-center gap-2">
      <span class="text-xs text-kawaii-ink-muted"></span>
      <span class="kawaii-badge kawaii-badge--soft"></span>
    </div>`;
  article.querySelector('span').textContent = new Date(e.occurred_at).toLocaleString();
  article.querySelectorAll('span')[1].textContent = e.event_type;
  return article;
}

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-profile-tabs]');
  if (!root) return;

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

  try {
    const data = await apiGet('/api/v1/profile/me');
    if (!data) return;

    const scopes = data.identity?.scopes?.join(', ') || '-';
    const expiry = data.identity?.expires_at
      ? new Date(data.identity.expires_at).toLocaleDateString()
      : '-';

    const scopesEl = document.getElementById('profile-scopes');
    const expiryEl = document.getElementById('profile-token-expiry');
    if (scopesEl) scopesEl.textContent = `${uiText('profile_scopes', '权限')}: ${scopes}`;
    if (expiryEl) expiryEl.textContent = `${uiText('profile_token_expiry', 'Token 有效期')}: ${expiry}`;

    const skillsList = document.getElementById('profile-skills-list');
    if (skillsList && data.accessible_skills?.length) {
      skillsList.replaceChildren(...data.accessible_skills.map(createSkillCard));
    } else if (skillsList) {
      skillsList.innerHTML = `
        <div class="kawaii-card animate-in text-center py-8 text-kawaii-ink-muted text-sm">
          ${escapeHtml(uiText('profile_no_skills', '暂无可访问技能'))}
        </div>`;
    }

    const historyList = document.getElementById('profile-history-list');
    if (historyList && data.operation_history?.length) {
      historyList.replaceChildren(...data.operation_history.map(createHistoryCard));
    }

    const policyList = document.getElementById('profile-policy-list');
    if (policyList && data.policy && Object.keys(data.policy).length) {
      const pre = document.createElement('pre');
      pre.className = 'text-xs text-kawaii-ink-soft overflow-x-auto';
      pre.textContent = JSON.stringify(data.policy, null, 2);
      const article = document.createElement('article');
      article.className = 'kawaii-card animate-in';
      article.appendChild(pre);
      policyList.replaceChildren(article);
    }
  } catch (err) {
    console.error('Failed to load profile:', err);
  }
});
