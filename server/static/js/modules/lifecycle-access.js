/**
 * Access checks
 */
import {
  uiText,
  currentPageLanguage,
} from './config.js';
import {
  apiGet,
} from './api.js';

// ── Shared toast (injected from lifecycle.js) ───────────────────────
let toastRef = null;
export function setAccessToastRef(ref) { toastRef = ref; }
const _toast = {
  error: (msg, dur) => { if (toastRef) toastRef.error(msg, dur); },
};

export async function checkAccessMe() {
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

export async function checkReleaseAccess(releaseId) {
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
    metaSpan.className = 'access-check-meta';
    const metaItems = [
      [labelOk, data.ok === true ? 'true' : (data.ok === false ? 'false' : '-')],
      [labelCredentialType, data.credential_type || '-'],
      [labelPrincipalId, data.principal_id || '-'],
      [labelScopeGranted, scopeValue],
    ];
    metaItems.forEach(([label, value]) => {
      const line = document.createElement('span');
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
