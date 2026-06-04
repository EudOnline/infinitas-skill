/**
 * Exposure CRUD and Review operations
 */
import {
  uiText,
  uiTemplate,
  currentPageLanguage,
  sanitizeClassName,
} from './config.js';
import {
  apiPost,
  apiPatch,
  apiGet,
} from './api.js';
import {
  formatAudienceType,
} from './search.js';

// ── Shared toast + helpers (injected from lifecycle.js) ─────────────
let toastRef = null;
export function setExposureToastRef(ref) { toastRef = ref; }
const _toast = {
  success: (msg, dur) => { if (toastRef) toastRef.success(msg, dur); },
  error: (msg, dur) => { if (toastRef) toastRef.error(msg, dur); },
};

let _setButtonLoading = () => {};
let _reloadWithToast = () => {};

export function setExposureHelpers({ setButtonLoading, reloadWithToast }) {
  _setButtonLoading = setButtonLoading;
  _reloadWithToast = reloadWithToast;
}

// ── Exposure CRUD ───────────────────────────────────────────────────

export async function createExposure(form) {
  const releaseId = form.dataset.releaseId;
  const button = form.querySelector('button[type="submit"]');
  _setButtonLoading(button, true);
  try {
    const data = {
      audience_type: form.elements.audience_type.value,
      listing_mode: form.elements.listing_mode.value,
      install_mode: form.elements.install_mode.value,
      requested_review_mode: form.elements.requested_review_mode.value,
    };
    await apiPost(`/api/v1/releases/${encodeURIComponent(releaseId)}/exposures`, data);
    _reloadWithToast('success', uiText('exposure_created', '分享出口创建成功'));
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('exposure_create_error', '创建分享出口失败'));
  }
}

export async function patchExposure(exposureId, form) {
  const button = form.querySelector('button[type="submit"]');
  _setButtonLoading(button, true);
  try {
    const data = {};
    if (form.elements.listing_mode) data.listing_mode = form.elements.listing_mode.value;
    if (form.elements.install_mode) data.install_mode = form.elements.install_mode.value;
    if (form.elements.requested_review_mode) data.requested_review_mode = form.elements.requested_review_mode.value;
    await apiPatch(`/api/v1/exposures/${encodeURIComponent(exposureId)}`, data);
    _reloadWithToast('success', uiText('exposure_patched', '分享设置已更新'));
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('exposure_patch_error', '更新分享设置失败'));
  }
}

export function syncExposureReviewModePolicy() {
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

export async function activateExposure(exposureId, button) {
  _setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/exposures/${encodeURIComponent(exposureId)}/activate`, {});
    _reloadWithToast('success', uiText('exposure_activated', '分享已激活'));
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('exposure_activate_error', '激活分享失败'));
  }
}

export async function revokeExposure(exposureId, button) {
  _setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/exposures/${encodeURIComponent(exposureId)}/revoke`, {});
    _reloadWithToast('success', uiText('exposure_revoked', '分享已撤销'));
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('exposure_revoke_error', '撤销分享失败'));
  }
}

// ── Review ──────────────────────────────────────────────────────────

export async function submitReviewDecision(reviewCaseId, decision, note = '', button) {
  _setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/review-cases/${encodeURIComponent(reviewCaseId)}/decisions`, { decision, note, evidence: {} });
    const msgMap = {
      approve: uiText('review_approved', '审核已通过'),
      reject: uiText('review_rejected', '审核已驳回'),
      comment: uiText('review_commented', '备注已添加'),
    };
    _reloadWithToast('success', msgMap[decision] || msgMap.comment);
  } catch (err) {
    _setButtonLoading(button, false);
    _toast.error(err.message || uiText('review_decision_error', '提交审核决定失败'));
  }
}

export async function toggleReviewDetail(reviewCaseId, button) {
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

  _setButtonLoading(button, true);
  let opened = false;
  try {
    const data = await apiGet(`/api/v1/review-cases/${encodeURIComponent(reviewCaseId)}`);
    renderReviewDetail(content, data);
    row.hidden = false;
    opened = true;
  } catch (err) {
    _toast.error(err.message || uiText('review_detail_error', '加载详情失败'));
  } finally {
    _setButtonLoading(button, false);
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
