/**
 * Lifecycle page initializers — facade that re-exports from sub-modules.
 */
import { uiText, currentPageLanguage } from './config.js';
import {
  setCrudToastRef,
  setCrudHelpers,
  createSkill,
  createDraft,
  saveDraft,
  sealDraft,
  createRelease,
  pollReleaseReady,
} from './lifecycle-crud.js';
import {
  setExposureToastRef,
  setExposureHelpers,
  createExposure,
  patchExposure,
  syncExposureReviewModePolicy,
  activateExposure,
  revokeExposure,
  submitReviewDecision,
  toggleReviewDetail,
} from './lifecycle-exposure.js';
import {
  setAccessToastRef,
  checkAccessMe,
  checkReleaseAccess,
} from './lifecycle-access.js';

// ── Toast reference (set by the application bootstrap) ──────────────
let toastRef = null;
export function setLifecycleToastRef(ref) {
  toastRef = ref;
  setCrudToastRef(ref);
  setExposureToastRef(ref);
  setAccessToastRef(ref);
}

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
    if (btnIcon) btnIcon.textContent = '⏳';
    if (btnText) btnText.textContent = uiText('loading', '处理中…');
  } else {
    button.removeAttribute('aria-busy');
    button.classList.remove('kawaii-button--loading');
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

// Inject shared helpers into sub-modules
setCrudHelpers({ setButtonLoading, preserveLang, reloadWithToast });
setExposureHelpers({ setButtonLoading, reloadWithToast });

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
    pollReleaseReady(releaseId);
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
