/**
 * Skill, Draft, and Release CRUD operations
 */
import {
  uiText,
  currentPageLanguage,
  logError,
} from './config.js';
import {
  apiGet,
  apiPost,
  apiPatch,
} from './api.js';

// ── Shared toast + helpers (injected from lifecycle.js) ─────────────
let toastRef = null;
export function setCrudToastRef(ref) { toastRef = ref; }
const _toast = {
  success: (msg, dur) => { if (toastRef) toastRef.success(msg, dur); },
  error: (msg, dur) => { if (toastRef) toastRef.error(msg, dur); },
};

let _setButtonLoading = () => {};
let _preserveLang = (p) => p;
let _reloadWithToast = () => {};

export function setCrudHelpers({ setButtonLoading, preserveLang, reloadWithToast }) {
  _setButtonLoading = setButtonLoading;
  _preserveLang = preserveLang;
  _reloadWithToast = reloadWithToast;
}

// ── Formatting helpers ──────────────────────────────────────────────

export function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

// ── Skill CRUD ──────────────────────────────────────────────────────

export async function createSkill(form) {
  const button = form.querySelector('button[type="submit"]');
  _setButtonLoading(button, true);
  try {
    const data = {
      slug: form.elements.slug.value.trim(),
      display_name: form.elements.display_name.value.trim(),
      summary: form.elements.summary.value.trim(),
      default_visibility_profile: form.elements.default_visibility_profile.value || null,
    };
    const result = await apiPost('/api/v1/skills', data);
    _toast.success(uiText('skill_created', '技能创建成功'));
    window.location.href = _preserveLang(`/skills/${result.id}`);
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('skill_create_error', '创建技能失败'));
  }
}

// ── Draft CRUD ──────────────────────────────────────────────────────

export async function createDraft(form) {
  const skillId = form.dataset.skillId;
  const button = form.querySelector('button[type="submit"]');
  _setButtonLoading(button, true);
  try {
    const baseVersionId = form.elements.base_version_id.value;
    const data = {
      content_ref: form.elements.content_ref.value.trim(),
      metadata: {},
    };
    if (baseVersionId) data.base_version_id = parseInt(baseVersionId, 10);
    try {
      data.metadata = JSON.parse(form.elements.metadata_json.value || '{}');
    } catch (_e) {
      _toast.error(uiText('invalid_json', 'JSON 格式错误'));
      _setButtonLoading(button, false);
      return;
    }
    const result = await apiPost(`/api/v1/skills/${encodeURIComponent(skillId)}/drafts`, data);
    _toast.success(uiText('draft_created', '草稿创建成功'));
    window.location.href = _preserveLang(`/drafts/${result.id}`);
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('draft_create_error', '创建草稿失败'));
  }
}

export async function saveDraft(form) {
  const draftId = form.dataset.draftId;
  const button = form.querySelector('button[type="submit"]');
  _setButtonLoading(button, true);
  try {
    const data = {};
    const contentRef = form.elements.content_ref.value.trim();
    if (contentRef) data.content_ref = contentRef;
    try {
      data.metadata = JSON.parse(form.elements.metadata_json.value || '{}');
    } catch (_e) {
      _toast.error(uiText('invalid_json', 'JSON 格式错误'));
      _setButtonLoading(button, false);
      return;
    }
    await apiPatch(`/api/v1/drafts/${encodeURIComponent(draftId)}`, data);
    _reloadWithToast('success', uiText('draft_saved', '草稿保存成功'));
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('draft_save_error', '保存草稿失败'));
  }
}

export async function sealDraft(form) {
  const draftId = form.dataset.draftId;
  const button = form.querySelector('button[type="submit"]');
  _setButtonLoading(button, true);
  try {
    const version = form.elements.version.value.trim();
    await apiPost(`/api/v1/drafts/${encodeURIComponent(draftId)}/seal`, { version });
    _reloadWithToast('success', uiText('draft_sealed', '草稿已封版'));
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('draft_seal_error', '封版失败'));
  }
}

// ── Release CRUD ────────────────────────────────────────────────────

export async function createRelease(versionId, button) {
  _setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/versions/${encodeURIComponent(versionId)}/releases`, {});
    _reloadWithToast('success', uiText('release_created', '发布创建成功'));
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('release_create_error', '创建发布失败'));
  }
}

export async function updateArtifactsTable(releaseId) {
  const section = document.getElementById('artifact-section');
  if (!section) return 0;
  try {
    const data = await apiGet(`/api/v1/releases/${encodeURIComponent(releaseId)}/artifacts`);
    const artifacts = Array.isArray(data) ? data : (data.items || []);
    const tableScroll = section.querySelector('.table-scroll');
    if (!tableScroll) return 0;

    let table = tableScroll.querySelector('table');
    if (!table && artifacts.length > 0) {
      const lang = currentPageLanguage();
      table = document.createElement('table');
      const thead = document.createElement('thead');
      const trHead = document.createElement('tr');
      [
        'ID',
        uiText('artifacts_kind', lang === 'en' ? 'Kind' : '类型'),
        'SHA256',
        uiText('artifacts_size', lang === 'en' ? 'Size' : '大小'),
        uiText('artifacts_storage_uri', lang === 'en' ? 'Storage URI' : '存储位置'),
      ].forEach((text) => {
        const th = document.createElement('th');
        th.textContent = text;
        trHead.appendChild(th);
      });
      thead.appendChild(trHead);
      table.appendChild(thead);
      table.appendChild(document.createElement('tbody'));
      tableScroll.replaceChildren();
      tableScroll.appendChild(table);
    }

    const tbody = table?.querySelector('tbody');
    if (!tbody) return 0;
    tbody.replaceChildren();
    artifacts.forEach((item) => {
      const tr = document.createElement('tr');
      const td1 = document.createElement('td');
      td1.textContent = item.id || '';
      const td2 = document.createElement('td');
      td2.textContent = item.kind || '';
      const td3 = document.createElement('td');
      const code3 = document.createElement('code');
      code3.className = 'table-code';
      code3.textContent = item.sha256 || '';
      td3.appendChild(code3);
      const td4 = document.createElement('td');
      td4.textContent = item.size_bytes ? formatBytes(item.size_bytes) : '';
      const td5 = document.createElement('td');
      const code5 = document.createElement('code');
      code5.className = 'table-code';
      code5.textContent = item.storage_uri || '';
      td5.appendChild(code5);
      tr.appendChild(td1);
      tr.appendChild(td2);
      tr.appendChild(td3);
      tr.appendChild(td4);
      tr.appendChild(td5);
      tbody.appendChild(tr);
    });
    return artifacts.length;
  } catch (err) {
    logError('load artifacts error:', err);
    return 0;
  }
}

export async function pollReleaseReady(releaseId, intervalMs = 3000) {
  const statusEl = document.getElementById('release-status');
  if (!statusEl) return () => {};
  statusEl.setAttribute('aria-live', 'polite');
  const ac = new AbortController();
  let timer = null;
  let attempts = 0;
  const maxAttempts = 120; // ~6 min at 3s interval
  const stop = () => {
    ac.abort();
    if (timer) clearTimeout(timer);
    window.removeEventListener('beforeunload', stop);
  };
  const check = async () => {
    try {
      const data = await apiGet(`/api/v1/releases/${encodeURIComponent(releaseId)}`, ac.signal);
      if (data.state === 'ready') {
        if (statusEl) {
          statusEl.textContent = uiText('release_ready', '已就绪');
          statusEl.classList.remove('kawaii-badge--pending');
          statusEl.classList.add('kawaii-badge--success');
        }
        const artifactSection = document.getElementById('artifact-section');
        if (artifactSection) artifactSection.hidden = false;
        const artifactCount = await updateArtifactsTable(releaseId);
        const lang = currentPageLanguage();
        const stateLabel = uiText('label_state', lang === 'en' ? 'State' : '状态');
        const artifactsLabel = uiText('label_artifacts', lang === 'en' ? 'Artifacts' : '产物');
        const readyText = uiText('release_ready', '已就绪');
        document.querySelectorAll('.page-stats .stat').forEach((stat) => {
          const label = stat.querySelector('.stat-label');
          if (!label) return;
          const valueEl = stat.querySelector('.stat-value');
          if (!valueEl) return;
          if (label.textContent.trim() === stateLabel) {
            valueEl.textContent = readyText;
          } else if (label.textContent.trim() === artifactsLabel) {
            valueEl.textContent = String(artifactCount || 0);
          }
        });
        _toast.success(uiText('release_is_ready', '发布产物已就绪'));
        stop();
        return;
      }
      if (ac.signal.aborted) return;
      if (++attempts >= maxAttempts) {
        stop();
        return;
      }
      timer = setTimeout(() => check(), intervalMs);
    } catch (err) {
      if (ac.signal.aborted) return;
      if (err.status === 403 || err.status === 404) {
        statusEl.textContent = uiText('release_poll_stopped', '状态刷新已停止');
        statusEl.classList.remove('kawaii-badge--pending', 'kawaii-badge--success');
        statusEl.classList.add('kawaii-badge--running');
        statusEl.dataset.state = 'error';
        _toast.error(err.message || uiText('generic_action_failed', '操作失败，请刷新页面重试'));
        stop();
        return;
      }
      logError('poll release error:', err);
      if (++attempts >= maxAttempts) {
        stop();
        return;
      }
      timer = setTimeout(() => check(), intervalMs * 2);
    }
  };
  window.addEventListener('beforeunload', stop);
  check();
  return stop;
}
