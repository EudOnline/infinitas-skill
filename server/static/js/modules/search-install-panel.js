import { bindCopyTriggers } from './api.js';
import { isSafeUrl, uiText } from './config.js';
import { formatAudienceType, formatInstallScope, formatListingMode } from './search-formatting.js';

function textElement(tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

function installHeader(data, skill) {
  const header = document.createElement('div');
  header.className = 'search-install-header';
  const title = document.createElement('div');
  title.className = 'search-install-title';
  title.append(
    textElement('div', 'search-install-name', data.display_name || data.name || ''),
    textElement('div', 'search-install-qualified', data.qualified_name || ''),
  );
  header.append(
    textElement('span', 'search-install-icon', skill.icon || '🎯'),
    title,
    textElement('span', 'search-install-version', data.version || ''),
  );
  return header;
}

function installMeta(data, skill) {
  const meta = document.createElement('div');
  meta.className = 'search-install-meta';
  if (data.summary) meta.appendChild(textElement('div', 'search-install-summary', data.summary));
  const rows = [
    [uiText('search_install_audience', '受众'), formatAudienceType(data.audience_type)],
    [uiText('search_install_publisher', 'Publisher'), data.publisher || '-'],
    [uiText('search_install_install_scope', 'Install scope'), formatInstallScope(skill.install_scope || data.install_scope) || '-'],
    [uiText('search_install_listing_mode', 'Listing mode'), formatListingMode(skill.listing_mode || data.listing_mode) || '-'],
    [uiText('search_install_runtime', 'Runtime'), skill.runtime?.platform || data.runtime?.platform || '-'],
    [uiText('search_install_readiness', 'Readiness'), skill.runtime_readiness || data.runtime_readiness || '-'],
    [uiText('search_install_workspace_targets', 'Workspace targets'), (skill.workspace_targets || data.workspace_targets || []).join(', ') || '-'],
    [uiText('search_install_bundle_sha256', 'Bundle SHA256'), data.bundle_sha256 || '-'],
  ];
  for (const [label, value] of rows) {
    const row = document.createElement('div');
    row.className = 'search-install-row';
    row.append(
      textElement('span', 'search-install-label', label),
      textElement('span', 'search-install-value', value),
    );
    meta.appendChild(row);
  }
  return meta;
}

function artifactLinks(data) {
  const links = document.createElement('div');
  links.className = 'search-install-links';
  const artifacts = [
    [uiText('search_install_manifest', '清单'), data.manifest_url],
    [uiText('search_install_bundle', '包'), data.bundle_url],
    [uiText('search_install_provenance', '来源'), data.provenance_url],
    [uiText('search_install_signature', '签名'), data.signature_url],
  ];
  for (const [label, url] of artifacts) {
    if (!url || !isSafeUrl(url)) continue;
    const link = textElement('a', 'kawaii-button kawaii-button--ghost search-install-link', label);
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener';
    links.appendChild(link);
  }
  return links;
}

function copyButton(text, value, className) {
  const button = textElement('button', className, text);
  button.type = 'button';
  button.dataset.copy = value;
  return button;
}

function installActions(data, skill) {
  const actions = document.createElement('div');
  actions.className = 'search-install-actions';
  if (skill.install_ref) {
    actions.appendChild(copyButton(
      uiText('search_install_copy_ref', '复制 install_ref'),
      skill.install_ref,
      'kawaii-button kawaii-button--secondary search-install-btn-sm',
    ));
  }
  if (skill.install_api_path) {
    actions.appendChild(copyButton(
      uiText('search_install_copy_api', '复制 API 路径'),
      skill.install_api_path,
      'kawaii-button kawaii-button--ghost search-install-btn-sm',
    ));
  }
  if (data.bundle_url && isSafeUrl(data.bundle_url)) {
    const link = textElement(
      'a',
      'kawaii-button kawaii-button--primary search-install-btn-sm',
      uiText('search_install_open_artifact', '打开产物'),
    );
    link.href = data.bundle_url;
    link.target = '_blank';
    link.rel = 'noopener';
    actions.appendChild(link);
  }
  return actions;
}

export function renderInstallPanel(dropdown, data, skill, goBack) {
  dropdown.replaceChildren();
  dropdown.setAttribute('role', 'dialog');
  dropdown.setAttribute('aria-label', uiText('search_install_panel_label', 'Skill install details'));
  const panel = document.createElement('div');
  panel.className = 'search-install-panel';
  const backButton = textElement('button', 'search-install-back', uiText('search_install_back', '← 返回'));
  backButton.type = 'button';
  backButton.addEventListener('click', (event) => {
    event.stopPropagation();
    goBack();
  });
  const divider = document.createElement('div');
  divider.className = 'search-install-divider';
  panel.append(
    backButton,
    installHeader(data, skill),
    installMeta(data, skill),
    divider,
    artifactLinks(data),
    installActions(data, skill),
  );
  dropdown.appendChild(panel);
  bindCopyTriggers(dropdown);
  setTimeout(() => backButton.focus(), 50);
}
