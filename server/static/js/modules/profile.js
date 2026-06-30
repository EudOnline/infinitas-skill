import { apiGet } from './api.js';
import { uiText } from './config.js';

function createSkillCard(s) {
  const article = document.createElement('article');
  article.className = 'kawaii-card animate-in';

  const wrapper = document.createElement('div');
  wrapper.className = 'flex items-center justify-between';

  const info = document.createElement('div');
  const h3 = document.createElement('h3');
  h3.className = 'font-display text-sm font-bold text-kawaii-ink';
  h3.textContent = s.display_name;
  const p = document.createElement('p');
  p.className = 'text-xs text-kawaii-ink-muted';
  p.textContent = `${s.slug} · ${s.kind}`;
  info.appendChild(h3);
  info.appendChild(p);

  const badge = document.createElement('span');
  badge.className = 'kawaii-badge kawaii-badge--success';
  badge.textContent = 'active';

  wrapper.appendChild(info);
  wrapper.appendChild(badge);
  article.appendChild(wrapper);
  return article;
}

function createHistoryCard(e) {
  const article = document.createElement('article');
  article.className = 'kawaii-card animate-in';
  const timeEl = document.createElement('span');
  timeEl.className = 'text-xs text-kawaii-ink-muted';
  timeEl.textContent = new Date(e.occurred_at).toLocaleString();
  const badgeEl = document.createElement('span');
  badgeEl.className = 'kawaii-badge kawaii-badge--soft';
  badgeEl.textContent = e.event_type;
  const wrapper = document.createElement('div');
  wrapper.className = 'flex items-center gap-2';
  wrapper.append(timeEl, badgeEl);
  article.appendChild(wrapper);
  return article;
}

function showError(container, message) {
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'kawaii-card animate-in text-center py-8 text-kawaii-danger text-sm';
  el.textContent = message;
  container.replaceChildren(el);
}

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-profile-tabs]');
  if (!root) return;

  function activateProfileTab(btn) {
    root.querySelectorAll('[data-tab]').forEach((b) => {
      const isActive = b === btn;
      b.classList.toggle('is-active', isActive);
      b.setAttribute('aria-selected', isActive ? 'true' : 'false');
      b.setAttribute('tabindex', isActive ? '0' : '-1');
    });

    document.querySelectorAll('[data-tab-panel]').forEach((panel) => {
      panel.classList.toggle('hidden', panel.dataset.tabPanel !== btn.dataset.tab);
    });
    btn.focus();
  }

  root.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-tab]');
    if (!btn) return;
    activateProfileTab(btn);
  });

  // WAI-ARIA Tabs keyboard navigation
  root.addEventListener('keydown', (e) => {
    const btn = e.target.closest('[data-tab]');
    if (!btn) return;
    const allTabs = Array.from(root.querySelectorAll('[data-tab]'));
    const idx = allTabs.indexOf(btn);
    let next = -1;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      next = (idx + 1) % allTabs.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      next = (idx - 1 + allTabs.length) % allTabs.length;
    } else if (e.key === 'Home') {
      e.preventDefault();
      next = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      next = allTabs.length - 1;
    }
    if (next >= 0) {
      activateProfileTab(allTabs[next]);
    }
  });

  const skillsList = document.getElementById('profile-skills-list');
  const historyList = document.getElementById('profile-history-list');
  const policyList = document.getElementById('profile-policy-list');

  try {
    const data = await apiGet('/api/v1/profile/me');
    if (!data) {
      showError(skillsList, uiText('profile_load_error', '加载失败，请刷新重试'));
      return;
    }

    const scopes = data.identity?.scopes?.join(', ') || '-';
    const expiry = data.identity?.expires_at
      ? new Date(data.identity.expires_at).toLocaleDateString()
      : '-';

    const scopesEl = document.getElementById('profile-scopes');
    const expiryEl = document.getElementById('profile-token-expiry');
    if (scopesEl) scopesEl.textContent = `${uiText('profile_scopes', '权限')}: ${scopes}`;
    if (expiryEl) expiryEl.textContent = `${uiText('profile_token_expiry', 'Token 有效期')}: ${expiry}`;

    if (skillsList && data.accessible_skills?.length) {
      skillsList.replaceChildren(...data.accessible_skills.map(createSkillCard));
    } else if (skillsList) {
      const emptyDiv = document.createElement('div');
      emptyDiv.className = 'kawaii-card animate-in text-center py-8 text-kawaii-ink-muted text-sm';
      emptyDiv.textContent = uiText('profile_no_skills', '暂无可访问技能');
      skillsList.replaceChildren(emptyDiv);
    }

    if (historyList && data.operation_history?.length) {
      historyList.replaceChildren(...data.operation_history.map(createHistoryCard));
    }

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
    showError(skillsList, uiText('profile_load_error', '加载失败，请刷新重试'));
  }
});
