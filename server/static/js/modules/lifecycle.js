/**
 * Lifecycle CRUD functions and page initializers
 */
import {
  uiText,
  uiTemplate,
  currentPageLanguage,
  sanitizeClassName,
} from './config.js';
import {
  apiGet,
  apiPost,
  apiPatch,
} from './api.js';
import {
  formatAudienceType,
  formatInstallScope,
  formatListingMode,
} from './search.js';

// ── Toast reference (set by the application bootstrap) ──────────────
let toastRef = null;
export function setLifecycleToastRef(ref) { toastRef = ref; }
const _toast = {
  success: (msg, dur) => { if (toastRef) _toast.success(msg, dur); },
  error: (msg, dur) => { if (toastRef) _toast.error(msg, dur); },
  info: (msg, dur) => { if (toastRef) toastRef.info(msg, dur); },
  warning: (msg, dur) => { if (toastRef) toastRef.warning(msg, dur); },
};

// ── Button / navigation helpers ─────────────────────────────────────

function setButtonLoading(button, loading) {
  if (!button) return;
  const btnIcon = button.querySelector('.btn-icon');
  const btnText = button.querySelector('.btn-text');
  if (loading) {
    if (button.getAttribute('aria-busy') !== 'true') {
      button.dataset.originalText = btnText ? btnText.textContent : '';
      button.dataset.originalIcon = btnIcon ? btnIcon.textContent : '';
    }
    button.setAttribute('aria-busy', 'true');
    button.classList.add('kawaii-button--loading');
    button.style.opacity = '0.7';
    button.style.pointerEvents = 'none';
    if (btnIcon) btnIcon.textContent = '⏳';
    if (btnText) btnText.textContent = uiText('loading', '处理中…');
  } else {
    button.removeAttribute('aria-busy');
    button.classList.remove('kawaii-button--loading');
    button.style.opacity = '';
    button.style.pointerEvents = '';
    if (btnIcon) btnIcon.textContent = button.dataset.originalIcon || '';
    if (btnText) btnText.textContent = button.dataset.originalText || '';
  }
}

function preserveLang(path) {
  const lang = currentPageLanguage();
  if (!lang) return path;
  const url = new URL(path, window.location.origin);
  url.searchParams.set('lang', lang);
  return url.pathname + url.search;
}

function reloadWithToast(type, message, delay = 600) {
  const key = `lifecycle_toast_${Date.now()}`;
  try {
    sessionStorage.setItem(key, JSON.stringify({ type, message, ts: Date.now() }));
  } catch (_e) {}
  setTimeout(() => { window.location.href = preserveLang(window.location.pathname + window.location.search); }, delay);
}

// ── Formatting helpers ──────────────────────────────────────────────
// formatAudienceType, formatInstallScope, formatListingMode imported from search.js

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

// ── Skill CRUD ──────────────────────────────────────────────────────

async function createSkill(form) {
  const button = form.querySelector('button[type="submit"]');
  setButtonLoading(button, true);
  try {
    const data = {
      slug: form.elements.slug.value.trim(),
      display_name: form.elements.display_name.value.trim(),
      summary: form.elements.summary.value.trim(),
      default_visibility_profile: form.elements.default_visibility_profile.value || null,
    };
    const result = await apiPost('/api/v1/skills', data);
    _toast.success(uiText('skill_created', '技能创建成功'));
    window.location.href = preserveLang(`/skills/${result.id}`);
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('skill_create_error', '创建技能失败'));
  }
}

// ── Draft CRUD ──────────────────────────────────────────────────────

async function createDraft(form) {
  const skillId = form.dataset.skillId;
  const button = form.querySelector('button[type="submit"]');
  setButtonLoading(button, true);
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
      setButtonLoading(button, false);
      return;
    }
    const result = await apiPost(`/api/v1/skills/${encodeURIComponent(skillId)}/drafts`, data);
    _toast.success(uiText('draft_created', '草稿创建成功'));
    window.location.href = preserveLang(`/drafts/${result.id}`);
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('draft_create_error', '创建草稿失败'));
  }
}

async function saveDraft(form) {
  const draftId = form.dataset.draftId;
  const button = form.querySelector('button[type="submit"]');
  setButtonLoading(button, true);
  try {
    const data = {};
    const contentRef = form.elements.content_ref.value.trim();
    if (contentRef) data.content_ref = contentRef;
    try {
      data.metadata = JSON.parse(form.elements.metadata_json.value || '{}');
    } catch (_e) {
      _toast.error(uiText('invalid_json', 'JSON 格式错误'));
      setButtonLoading(button, false);
      return;
    }
    await apiPatch(`/api/v1/drafts/${encodeURIComponent(draftId)}`, data);
    reloadWithToast('success', uiText('draft_saved', '草稿保存成功'));
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('draft_save_error', '保存草稿失败'));
  }
}

async function sealDraft(form) {
  const draftId = form.dataset.draftId;
  const button = form.querySelector('button[type="submit"]');
  setButtonLoading(button, true);
  try {
    const version = form.elements.version.value.trim();
    await apiPost(`/api/v1/drafts/${encodeURIComponent(draftId)}/seal`, { version });
    reloadWithToast('success', uiText('draft_sealed', '草稿已封版'));
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('draft_seal_error', '封版失败'));
  }
}

// ── Release CRUD ────────────────────────────────────────────────────

async function createRelease(versionId, button) {
  setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/versions/${encodeURIComponent(versionId)}/releases`, {});
    reloadWithToast('success', uiText('release_created', '发布创建成功'));
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('release_create_error', '创建发布失败'));
  }
}

async function updateArtifactsTable(releaseId) {
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
    console.error('load artifacts error:', err);
    return 0;
  }
}

async function pollReleaseReady(releaseId, intervalMs = 3000) {
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
      console.error('poll release error:', err);
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

// ── Exposure CRUD ───────────────────────────────────────────────────

async function createExposure(form) {
  const releaseId = form.dataset.releaseId;
  const button = form.querySelector('button[type="submit"]');
  setButtonLoading(button, true);
  try {
    const data = {
      audience_type: form.elements.audience_type.value,
      listing_mode: form.elements.listing_mode.value,
      install_mode: form.elements.install_mode.value,
      requested_review_mode: form.elements.requested_review_mode.value,
    };
    await apiPost(`/api/v1/releases/${encodeURIComponent(releaseId)}/exposures`, data);
    reloadWithToast('success', uiText('exposure_created', '分享出口创建成功'));
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('exposure_create_error', '创建分享出口失败'));
  }
}

async function patchExposure(exposureId, form) {
  const button = form.querySelector('button[type="submit"]');
  setButtonLoading(button, true);
  try {
    const data = {};
    if (form.elements.listing_mode) data.listing_mode = form.elements.listing_mode.value;
    if (form.elements.install_mode) data.install_mode = form.elements.install_mode.value;
    if (form.elements.requested_review_mode) data.requested_review_mode = form.elements.requested_review_mode.value;
    await apiPatch(`/api/v1/exposures/${encodeURIComponent(exposureId)}`, data);
    reloadWithToast('success', uiText('exposure_patched', '分享设置已更新'));
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('exposure_patch_error', '更新分享设置失败'));
  }
}

function syncExposureReviewModePolicy() {
  const form = document.getElementById('create-exposure-form');
  if (!form) return;

  const audienceSelect = document.getElementById('exposure-audience-type');
  const reviewModeSelect = form.elements.requested_review_mode;
  const publicWarning = document.getElementById('public-exposure-warning');
  const hintEl = document.getElementById('exposure-review-policy-hint');
  if (!audienceSelect || !reviewModeSelect) return;

  let exposurePolicy = {};
  try {
    const policyScript = document.getElementById('exposure-policy-data');
    exposurePolicy = JSON.parse(policyScript ? (policyScript.dataset.json || '{}') : '{}');
  } catch (_e) {}
  const release = { exposure_policy: exposurePolicy };

  const renderHint = (policy, audienceType) => {
    if (!hintEl) return;
    if (!policy) {
      hintEl.hidden = true;
      hintEl.replaceChildren();
      return;
    }

    const lang = currentPageLanguage();
    const audienceLabel = formatAudienceType(audienceType) || audienceType;
    const requirement = policy.effective_review_requirement;
    if (!requirement) {
      hintEl.hidden = true;
      hintEl.replaceChildren();
      return;
    }

    const requirementLabel = requirement === 'blocking'
      ? uiText('review_requirement_blocking', lang === 'en' ? 'Blocking review' : '阻塞审核')
      : uiText('review_requirement_none', lang === 'en' ? 'No review' : '无需审核');
    const prefix = uiTemplate('review_hint_prefix', lang === 'en' ? '{audience} exposures use' : '{audience} exposure 固定使用', { audience: audienceLabel });
    const badgeClass = requirement === 'blocking' ? 'kawaii-badge--pending' : 'kawaii-badge--success';
    hintEl.hidden = false;
    const badge = document.createElement('span');
    badge.className = `kawaii-badge ${badgeClass}`;
    badge.textContent = `${prefix} ${requirementLabel}`;
    hintEl.replaceChildren(badge);
  };

  const applyPolicy = () => {
    const audienceType = audienceSelect.value;
    const policy = release.exposure_policy[audienceType] || null;
    reviewModeSelect.disabled = false;

    const allowedModes = Array.isArray(policy?.allowed_requested_review_modes)
      ? policy.allowed_requested_review_modes
      : ['none', 'advisory', 'blocking'];
    Array.from(reviewModeSelect.options).forEach((option) => {
      const allowed = allowedModes.includes(option.value);
      option.disabled = !allowed;
      option.hidden = !allowed;
    });

    if (policy && policy.effective_requested_review_mode) {
      reviewModeSelect.value = policy.effective_requested_review_mode;
    } else if (!allowedModes.includes(reviewModeSelect.value)) {
      reviewModeSelect.value = allowedModes[0] || 'none';
    }

    if (policy && allowedModes.length === 1) {
      reviewModeSelect.disabled = true;
    }

    publicWarning.hidden = audienceType !== 'public';
    renderHint(policy, audienceType);
  };

  audienceSelect.addEventListener('change', applyPolicy);
  applyPolicy();
}

async function activateExposure(exposureId, button) {
  setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/exposures/${encodeURIComponent(exposureId)}/activate`, {});
    reloadWithToast('success', uiText('exposure_activated', '分享已激活'));
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('exposure_activate_error', '激活分享失败'));
  }
}

async function revokeExposure(exposureId, button) {
  setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/exposures/${encodeURIComponent(exposureId)}/revoke`, {});
    reloadWithToast('success', uiText('exposure_revoked', '分享已撤销'));
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('exposure_revoke_error', '撤销分享失败'));
  }
}

// ── Review ──────────────────────────────────────────────────────────

async function submitReviewDecision(reviewCaseId, decision, note = '', button) {
  setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/review-cases/${encodeURIComponent(reviewCaseId)}/decisions`, { decision, note, evidence: {} });
    const msgMap = {
      approve: uiText('review_approved', '审核已通过'),
      reject: uiText('review_rejected', '审核已驳回'),
      comment: uiText('review_commented', '备注已添加'),
    };
    reloadWithToast('success', msgMap[decision] || msgMap.comment);
  } catch (err) {
    setButtonLoading(button, false);
    _toast.error(err.message || uiText('review_decision_error', '提交审核决定失败'));
  }
}

async function toggleReviewDetail(reviewCaseId, button) {
  const row = document.getElementById(`review-detail-row-${encodeURIComponent(reviewCaseId)}`);
  const content = document.getElementById(`review-detail-content-${encodeURIComponent(reviewCaseId)}`);
  if (!row || !content) return;

  const isHidden = row.hidden;
  if (!isHidden) {
    row.hidden = true;
    button.textContent = uiText('review_detail_history', currentPageLanguage() === 'en' ? 'History' : '详情');
    button.focus();
    return;
  }

  if (!button.dataset.originalText) {
    button.dataset.originalText = button.textContent;
  }

  setButtonLoading(button, true);
  let opened = false;
  try {
    const data = await apiGet(`/api/v1/review-cases/${encodeURIComponent(reviewCaseId)}`);
    renderReviewDetail(content, data);
    row.hidden = false;
    opened = true;
  } catch (err) {
    _toast.error(err.message || uiText('review_detail_error', '加载详情失败'));
  } finally {
    setButtonLoading(button, false);
    if (opened) {
      button.textContent = uiText('review_detail_hide', currentPageLanguage() === 'en' ? 'Hide' : '收起');
    }
  }
}

function renderReviewDetail(container, data) {
  const lang = currentPageLanguage();
  const stateLabel = uiText('label_state', lang === 'en' ? 'State' : '状态');
  const emptyLabel = uiText('review_empty_label', lang === 'en' ? 'No decisions yet.' : '暂无决定记录。');
  const noteLabel = uiText('review_note_label', lang === 'en' ? 'Note' : '备注');

  const state = data.state || '-';
  const decisions = Array.isArray(data.decisions) ? data.decisions : [];

  const frag = document.createDocumentFragment();

  const stateDiv = document.createElement('div');
  stateDiv.className = 'review-detail-state';
  stateDiv.appendChild(document.createTextNode(stateLabel + ': '));
  const strong = document.createElement('strong');
  strong.textContent = state;
  stateDiv.appendChild(strong);
  frag.appendChild(stateDiv);

  if (decisions.length === 0) {
    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'review-detail-empty';
    emptyDiv.textContent = emptyLabel;
    frag.appendChild(emptyDiv);
  } else {
    const listDiv = document.createElement('div');
    listDiv.className = 'review-detail-list';
    decisions.forEach((d) => {
      const decision = d.decision || '-';
      const note = d.note || '';
      const evidence = d.evidence && Object.keys(d.evidence).length > 0 ? JSON.stringify(d.evidence, null, 2) : '';
      const createdAt = d.created_at || '';

      const item = document.createElement('div');
      item.className = 'review-detail-item';

      const meta = document.createElement('div');
      meta.className = 'review-detail-meta';
      const badge = document.createElement('span');
      badge.className = `review-detail-badge review-detail-badge--${sanitizeClassName(decision)}`;
      badge.textContent = decision;
      const dateSpan = document.createElement('span');
      dateSpan.textContent = createdAt;
      meta.appendChild(badge);
      meta.appendChild(dateSpan);
      item.appendChild(meta);

      if (note) {
        const noteDiv = document.createElement('div');
        noteDiv.className = 'review-detail-note';
        const strongNote = document.createElement('strong');
        strongNote.textContent = noteLabel + ':';
        noteDiv.appendChild(strongNote);
        noteDiv.appendChild(document.createTextNode(' ' + note));
        item.appendChild(noteDiv);
      }

      if (evidence) {
        const evDiv = document.createElement('div');
        evDiv.className = 'review-detail-evidence';
        const pre = document.createElement('pre');
        pre.textContent = evidence;
        evDiv.appendChild(pre);
        item.appendChild(evDiv);
      }

      listDiv.appendChild(item);
    });
    frag.appendChild(listDiv);
  }

  container.replaceChildren();
  container.appendChild(frag);
}

// ── Access checks ───────────────────────────────────────────────────

async function checkAccessMe() {
  const container = document.getElementById('access-me');
  if (!container) return;
  const lang = currentPageLanguage();
  try {
    const data = await apiGet('/api/v1/access/me');
    const grid = document.createElement('div');
    grid.className = 'access-me-grid';
    const fields = [
      [uiText('label_principal', lang === 'en' ? 'Principal / 主体' : '主体 / Principal'), data.principal_slug || '-'],
      [uiText('label_username', lang === 'en' ? 'Username / 用户名' : '用户名 / Username'), data.username || '-'],
      [uiText('label_scopes', lang === 'en' ? 'Scopes / 作用域' : '作用域 / Scopes'), (data.scopes || []).join(', ') || '-'],
    ];
    fields.forEach(([label, value]) => {
      const row = document.createElement('div');
      const lbl = document.createElement('span');
      lbl.className = 'access-me-label';
      lbl.textContent = label;
      const val = document.createElement('span');
      val.className = 'access-me-value';
      val.textContent = value;
      row.appendChild(lbl);
      row.appendChild(val);
      grid.appendChild(row);
    });
    container.replaceChildren(grid);
  } catch (err) {
    container.textContent = uiText('access_me_error', lang === 'en' ? 'Unable to load identity / 无法加载身份信息' : '无法加载身份信息 / Unable to load identity');
  }
}

async function checkReleaseAccess(releaseId) {
  const container = document.getElementById('release-access-check');
  if (!container) return;
  const lang = currentPageLanguage();
  if (!releaseId) {
    const errBadge1 = document.createElement('span');
    errBadge1.className = 'kawaii-badge kawaii-badge--error';
    errBadge1.textContent = uiText('access_input_required', lang === 'en' ? 'Please enter Release ID / 请输入发布 ID' : '请输入发布 ID / Please enter Release ID');
    container.replaceChildren(errBadge1);
    return;
  }
  try {
    const data = await apiGet(`/api/v1/access/releases/${encodeURIComponent(releaseId)}/check`);
    const okText = uiText('access_ok', lang === 'en' ? 'Access granted' : '有访问权限');
    const labelOk = uiText('label_ok', lang === 'en' ? 'ok / 状态' : '状态 / ok');
    const labelCredentialType = uiText('label_credential_type', lang === 'en' ? 'credential_type / 凭证类型' : '凭证类型 / credential_type');
    const labelPrincipalId = uiText('label_principal_id', lang === 'en' ? 'principal_id / 主体 ID' : '主体 ID / principal_id');
    const labelScopeGranted = uiText('label_scope_granted', lang === 'en' ? 'scope_granted / 授权范围' : '授权范围 / scope_granted');
    const scopeValue = Array.isArray(data.scope_granted) ? data.scope_granted.join(', ') : (data.scope_granted || '-');
    const okBadge = document.createElement('span');
    okBadge.className = 'kawaii-badge kawaii-badge--success';
    okBadge.textContent = okText;
    const metaSpan = document.createElement('span');
    metaSpan.style.cssText = 'display:inline-block;vertical-align:top;margin-left:0.5rem;font-size:0.85rem;color:var(--kawaii-ink-soft);line-height:1.5;';
    const metaItems = [
      [labelOk, data.ok === true ? 'true' : (data.ok === false ? 'false' : '-')],
      [labelCredentialType, data.credential_type || '-'],
      [labelPrincipalId, data.principal_id || '-'],
      [labelScopeGranted, scopeValue],
    ];
    metaItems.forEach(([label, value]) => {
      const line = document.createElement('span');
      line.style.display = 'block';
      const strong = document.createElement('strong');
      strong.textContent = label + ':';
      line.appendChild(strong);
      line.appendChild(document.createTextNode(' ' + value));
      metaSpan.appendChild(line);
    });
    container.replaceChildren(okBadge, metaSpan);
  } catch (err) {
    const errBadge2 = document.createElement('span');
    errBadge2.className = 'kawaii-badge kawaii-badge--error';
    errBadge2.textContent = uiText('access_denied', lang === 'en' ? 'Access denied / 无访问权限' : '无访问权限 / Access denied');
    container.replaceChildren(errBadge2);
    _toast.error(err.message || uiText('access_check_error', lang === 'en' ? 'Check failed / 检查失败' : '检查失败 / Check failed'));
  }
}

// ── Delegated action handlers (click / submit) ──────────────────────

function handleCreateReleaseClick(e) {
  const btn = e.target.closest('[data-action="create-release"]');
  if (!btn) return;
  const versionId = btn.dataset.versionId;
  if (versionId) createRelease(versionId, btn);
}

function handleShareDetailClick(e) {
  const activateBtn = e.target.closest('[data-action="activate-exposure"]');
  if (activateBtn) {
    activateExposure(activateBtn.dataset.exposureId, activateBtn);
    return;
  }
  const revokeBtn = e.target.closest('[data-action="revoke-exposure"]');
  if (revokeBtn) {
    revokeExposure(revokeBtn.dataset.exposureId, revokeBtn);
    return;
  }
  const patchToggle = e.target.closest('[data-action="toggle-patch-form"]');
  if (patchToggle) {
    const row = document.getElementById(`patch-form-row-${patchToggle.dataset.exposureId}`);
    if (row) row.hidden = !row.hidden;
  }
}

function handleShareDetailSubmit(e) {
  const form = e.target.closest('[data-action="patch-exposure"]');
  if (!form) return;
  e.preventDefault();
  patchExposure(form.dataset.exposureId, form);
}

function handleReviewCaseClick(e) {
  const formToggle = e.target.closest('[data-action="toggle-review-form"]');
  if (formToggle) {
    const row = document.getElementById(`review-form-row-${formToggle.dataset.reviewCaseId}`);
    if (row) row.hidden = !row.hidden;
    return;
  }
  const detailBtn = e.target.closest('[data-action="review-detail"]');
  if (detailBtn) {
    toggleReviewDetail(detailBtn.dataset.reviewCaseId, detailBtn);
    return;
  }
  const approveBtn = e.target.closest('[data-action="review-approve"]');
  if (approveBtn) {
    const caseId = approveBtn.dataset.reviewCaseId;
    const note = document.getElementById(`review-note-${caseId}`)?.value || '';
    submitReviewDecision(caseId, 'approve', note, approveBtn);
    return;
  }
  const rejectBtn = e.target.closest('[data-action="review-reject"]');
  if (rejectBtn) {
    const caseId = rejectBtn.dataset.reviewCaseId;
    const note = document.getElementById(`review-note-${caseId}`)?.value || '';
    submitReviewDecision(caseId, 'reject', note, rejectBtn);
    return;
  }
  const commentBtn = e.target.closest('[data-action="review-comment"]');
  if (commentBtn) {
    const caseId = commentBtn.dataset.reviewCaseId;
    const note = document.getElementById(`review-note-${caseId}`)?.value || '';
    submitReviewDecision(caseId, 'comment', note, commentBtn);
  }
}

function handleAccessTokensClick(e) {
  const btn = e.target.closest('[data-action="check-release-access"]');
  if (!btn) return;
  const input = document.getElementById('release-access-id');
  checkReleaseAccess(input?.value || '');
}

// ── Page initializers (exported) ────────────────────────────────────

export function initDelegatedActions() {
  document.body.addEventListener('click', (e) => {
    handleCreateReleaseClick(e);
    handleShareDetailClick(e);
    handleReviewCaseClick(e);
    handleAccessTokensClick(e);
  });
  document.body.addEventListener('submit', (e) => {
    handleShareDetailSubmit(e);
  });
}

export function initCreateSkill() {
  const form = document.getElementById('create-skill-form');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    createSkill(form);
  });
}

export function initCreateDraft() {
  const form = document.getElementById('create-draft-form');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    createDraft(form);
  });
}

export function initDraftDetail() {
  const saveForm = document.getElementById('save-draft-form');
  if (saveForm) {
    saveForm.addEventListener('submit', (e) => {
      e.preventDefault();
      saveDraft(saveForm);
    });
  }
  const sealForm = document.getElementById('seal-draft-form');
  if (sealForm) {
    sealForm.addEventListener('submit', (e) => {
      e.preventDefault();
      sealDraft(sealForm);
    });
  }
}

export function initReleaseDetail() {
  const statusEl = document.getElementById('release-status');
  const releaseId = statusEl?.dataset.releaseId;
  if (statusEl && releaseId && statusEl.dataset.state === 'preparing') {
    window._releasePollStop = pollReleaseReady(releaseId);
  }
}

export function initShareDetail() {
  const createForm = document.getElementById('create-exposure-form');
  if (createForm) {
    createForm.addEventListener('submit', (e) => {
      e.preventDefault();
      createExposure(createForm);
    });
  }
  // click/submit handlers registered by initDelegatedActions
  syncExposureReviewModePolicy();
}

export function initAccessTokens() {
  checkAccessMe();
  // click handler registered by initDelegatedActions
}
