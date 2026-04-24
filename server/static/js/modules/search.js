/**
 * Search manager - global skill/command search with install panel
 */
import {
  currentPageLanguage,
  currentSearchScope,
  uiText,
  sanitizeClassName,
  isSafeUrl,
} from './config.js';
import { copyToClipboard, bindCopyTriggers, apiGet } from './api.js';

let toastRef = null;

export function setSearchToastRef(ref) {
  toastRef = ref;
}

// ---------------------------------------------------------------------------
// Formatting helpers (i18n-aware)
// ---------------------------------------------------------------------------

export function formatAudienceType(audienceType) {
  const lang = currentPageLanguage();
  const map = {
    private: { zh: '私人', en: 'Private' },
    authenticated: { zh: '已认证', en: 'Authenticated' },
    grant: { zh: '令牌共享', en: 'Shared by token' },
    public: { zh: '公开', en: 'Public' },
  };
  const entry = map[String(audienceType || '').toLowerCase()];
  return entry ? entry[lang] || entry.zh : (audienceType || '');
}

export function formatInstallScope(scope) {
  const lang = currentPageLanguage();
  const map = {
    public: { zh: '公开', en: 'Public' },
    me: { zh: '仅自己', en: 'Only me' },
    grant: { zh: '授权', en: 'Grant' },
  };
  const entry = map[String(scope || '').toLowerCase()];
  return entry ? entry[lang] || entry.zh : (scope || '');
}

export function formatListingMode(mode) {
  const lang = currentPageLanguage();
  const map = {
    listed: { zh: '已列出', en: 'Listed' },
    direct_only: { zh: '仅直链', en: 'Direct only' },
  };
  const entry = map[String(mode || '').toLowerCase()];
  return entry ? entry[lang] || entry.zh : (mode || '');
}

// ---------------------------------------------------------------------------
// SearchManager
// ---------------------------------------------------------------------------

export class SearchManager {
  constructor() {
    this.input = document.getElementById('global-search');
    this.dropdown = document.getElementById('search-dropdown');
    this.debounceTimer = null;
    this.selectedIndex = -1;
    this.searchId = 0;
    this.abortController = null;

    // Store bound handlers for cleanup
    this._handlers = {};

    if (this.input) {
      this.init();
    }
  }

  init() {
    // Bind handlers once for proper cleanup
    this._handlers.input = (e) => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => {
        this.search(e.target.value);
      }, 150);
    };

    this._handlers.keydown = (e) => {
      // Cmd/Ctrl + K to focus search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        this.input.focus();
      }

      // Escape to close (or back to results from install panel)
      if (e.key === 'Escape') {
        if (this.dropdown && this.dropdown.getAttribute('role') === 'dialog' && this.lastSearchData) {
          this.render(this.lastSearchData);
          this.open();
          if (this.input) this.input.focus();
          return;
        }
        this.close();
      }

      // Arrow navigation (skip if user is typing in another input/text field)
      if (this.dropdown && !this.dropdown.hidden) {
        const active = document.activeElement;
        const isOwnInput = active === this.input;
        if (!isOwnInput && (active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA' || active?.tagName === 'SELECT')) return;
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          this.selectNext();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          this.selectPrev();
        } else if (e.key === 'Enter') {
          e.preventDefault();
          this.activateSelected();
        }
      }
    };

    this._handlers.click = (e) => {
      if (!e.target.closest('.search-bar-wrapper')) {
        this.close();
      }
    };

    // Attach listeners
    this.input.addEventListener('input', this._handlers.input);
    document.addEventListener('keydown', this._handlers.keydown);
    document.addEventListener('click', this._handlers.click);
  }

  destroy() {
    // Clean up all event listeners
    if (this.input && this._handlers.input) {
      this.input.removeEventListener('input', this._handlers.input);
    }
    if (this._handlers.keydown) {
      document.removeEventListener('keydown', this._handlers.keydown);
    }
    if (this._handlers.click) {
      document.removeEventListener('click', this._handlers.click);
    }

    // Clear timers
    clearTimeout(this.debounceTimer);

    // Abort pending requests
    if (this.abortController) {
      this.abortController.abort();
    }
  }

  async search(query) {
    if (!query.trim()) {
      this.close();
      return;
    }

    // Cancel previous request
    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();

    const currentSearchId = ++this.searchId;

    try {
      const response = await fetch(
        `/api/search?q=${encodeURIComponent(query)}&lang=${encodeURIComponent(currentPageLanguage())}&scope=${encodeURIComponent(currentSearchScope())}`,
        { credentials: 'same-origin', signal: this.abortController.signal }
      );

      if (response.status === 401) {
        const error = new Error('Search requires authentication');
        error.code = 'SEARCH_AUTH_REQUIRED';
        throw error;
      }

      // Check if this is the latest request
      if (currentSearchId !== this.searchId) return;

      if (!response.ok) throw new Error('Search failed');

      const data = await response.json();

      // Check again after await
      if (currentSearchId !== this.searchId) return;

      this.render(data);
      this.open();
    } catch (err) {
      // Ignore abort errors
      if (err.name === 'AbortError') return;

      if (currentSearchId !== this.searchId) return;

      if (err.code === 'SEARCH_AUTH_REQUIRED') {
        this.close();
        if (toastRef) toastRef.info(uiText('search_auth_required', '请先登录后搜索私人技能库'));
        document.dispatchEvent(new CustomEvent('infinitas:auth-required'));
        return;
      }

      console.error('Search error:', err);
      this.render({ skills: [], commands: [] });
    }
  }

  render(data) {
    if (!this.dropdown) return;

    this.lastSearchData = data;

    // Clear previous content and reset ARIA
    this.dropdown.replaceChildren();
    this.dropdown.setAttribute('role', 'listbox');
    this.dropdown.setAttribute('aria-label', uiText('search_results_label', '搜索结果'));
    if (this.input) this.input.removeAttribute('aria-activedescendant');

    // Skills section
    if (data.skills && data.skills.length > 0) {
      const section = document.createElement('div');
      section.className = 'search-dropdown__section';
      section.setAttribute('role', 'group');
      section.setAttribute('aria-label', uiText('search_skills_label', '技能'));

      const heading = document.createElement('h4');
      heading.textContent = uiText('search_skills_label', '技能');
      heading.setAttribute('aria-hidden', 'true');
      section.appendChild(heading);

      const results = document.createElement('div');
      results.className = 'search-results';
      results.setAttribute('role', 'presentation');

      data.skills.forEach((skill, i) => {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'search-result';
        el.setAttribute('role', 'option');
        el.setAttribute('id', `search-option-${i}`);
        el.setAttribute('aria-selected', 'false');
        el.setAttribute('tabindex', '-1');
        el.dataset.index = i;
        const prefersInstallPanel = currentSearchScope() !== 'public';
        if (skill.install_api_path && prefersInstallPanel) {
          el.addEventListener('click', () => this.showSkillInstall(skill));
        } else {
          const inspectTarget = skill.qualified_name || skill.id || skill.name || '';
          const inspectCommand = inspectTarget ? `uv run infinitas discovery inspect ${inspectTarget} --json` : '';
          if (inspectCommand) {
            el.dataset.copy = inspectCommand;
          }
        }

        const icon = document.createElement('span');
        icon.className = 'search-result__icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = skill.icon || '🎯';

        const info = document.createElement('div');
        info.className = 'search-result__info';

        const name = document.createElement('div');
        name.className = 'search-result__name';
        name.textContent = skill.name;

        const desc = document.createElement('div');
        desc.className = 'search-result__desc';
        desc.textContent = skill.summary || '';

        info.appendChild(name);
        info.appendChild(desc);

        const badge = document.createElement('span');
        badge.className = 'search-result__badge';
        badge.textContent = skill.version || '';

        const meta = document.createElement('div');
        meta.className = 'search-result__meta';
        if (skill.runtime_readiness) {
          const readiness = document.createElement('span');
          readiness.className = 'search-result__readiness search-result__readiness--' + sanitizeClassName(skill.runtime_readiness);
          readiness.textContent = skill.runtime_readiness;
          meta.appendChild(readiness);
        }
        if (skill.runtime && skill.runtime.platform) {
          const platform = document.createElement('span');
          platform.className = 'search-result__platform';
          platform.textContent = skill.runtime.platform;
          meta.appendChild(platform);
        }
        if (skill.workspace_targets && skill.workspace_targets.length) {
          const targets = document.createElement('span');
          targets.className = 'search-result__targets';
          targets.textContent = skill.workspace_targets.join(', ');
          meta.appendChild(targets);
        }
        if (meta.hasChildNodes()) {
          info.appendChild(meta);
        }

        el.appendChild(icon);
        el.appendChild(info);
        el.appendChild(badge);

        results.appendChild(el);
      });

      section.appendChild(results);
      this.dropdown.appendChild(section);
    }

    // Commands section
    if (data.commands && data.commands.length > 0) {
      const section = document.createElement('div');
      section.className = 'search-dropdown__section';
      section.setAttribute('role', 'group');
      section.setAttribute('aria-label', uiText('search_commands_label', '命令'));

      const heading = document.createElement('h4');
      heading.textContent = uiText('search_commands_label', '命令');
      heading.setAttribute('aria-hidden', 'true');
      section.appendChild(heading);

      const results = document.createElement('div');
      results.className = 'search-results';
      results.setAttribute('role', 'presentation');

      const skillsOffset = data.skills?.length || 0;
      data.commands.forEach((cmd, i) => {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'search-result';
        el.setAttribute('role', 'option');
        el.setAttribute('id', `search-option-${skillsOffset + i}`);
        el.setAttribute('aria-selected', 'false');
        el.setAttribute('tabindex', '-1');
        el.dataset.index = skillsOffset + i;
        el.classList.add('cursor-pointer');

        const icon = document.createElement('span');
        icon.className = 'search-result__icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = '⌨️';

        const info = document.createElement('div');
        info.className = 'search-result__info';

        const name = document.createElement('div');
        name.className = 'search-result__name';
        name.textContent = cmd.name;

        const code = document.createElement('code');
        code.className = 'search-result__code';
        code.textContent = cmd.command;

        info.appendChild(name);
        info.appendChild(code);

        el.appendChild(icon);
        el.appendChild(info);

        // Safely bind click event
        el.dataset.copy = cmd.command;

        results.appendChild(el);
      });

      section.appendChild(results);
      this.dropdown.appendChild(section);
    }

    // Empty state
    if (!this.dropdown.hasChildNodes()) {
      const empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.setAttribute('role', 'status');
      empty.setAttribute('aria-live', 'polite');

      const icon = document.createElement('div');
      icon.className = 'search-empty__icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = '🔍';

      const text = document.createElement('p');
      text.textContent = uiText('search_empty_label', '未找到匹配结果');

      const trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'kawaii-button kawaii-button--primary';
      trigger.classList.add('search-empty-action');
      trigger.dataset.copy = uiText('search_create_command', 'scripts/new-skill.sh publisher/my-skill basic');
      trigger.textContent = uiText('search_create_label', '创建新技能');

      empty.appendChild(icon);
      empty.appendChild(text);
      empty.appendChild(trigger);

      this.dropdown.appendChild(empty);
    }

    bindCopyTriggers(this.dropdown);

    this.selectedIndex = -1;
  }

  async showSkillInstall(skill) {
    if (!skill.install_api_path) return;
    try {
      const data = await apiGet(skill.install_api_path);
      this.renderInstallPanel(data, skill);
    } catch (err) {
      if (toastRef) toastRef.error(err.message || uiText('generic_action_failed', '操作失败，请刷新页面重试'));
    }
  }

  renderInstallPanel(data, skill) {
    if (!this.dropdown) return;
    this.dropdown.replaceChildren();
    this.dropdown.setAttribute('role', 'dialog');
    this.dropdown.setAttribute('aria-label', uiText('search_install_panel_label', 'Skill install details'));

    const panel = document.createElement('div');
    panel.className = 'search-install-panel';

    const backBtn = document.createElement('button');
    backBtn.type = 'button';
    backBtn.className = 'search-install-back';
    backBtn.textContent = uiText('search_install_back', '← 返回');
    backBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (this.lastSearchData) {
        this.render(this.lastSearchData);
        this.open();
        if (this.input) this.input.focus();
      } else {
        this.close();
      }
    });

    const header = document.createElement('div');
    header.className = 'search-install-header';
    const iconSpan = document.createElement('span');
    iconSpan.className = 'search-install-icon';
    iconSpan.textContent = skill.icon || '🎯';
    const titleDiv = document.createElement('div');
    titleDiv.className = 'search-install-title';
    const nameDiv = document.createElement('div');
    nameDiv.className = 'search-install-name';
    nameDiv.textContent = data.display_name || data.name || '';
    const qualDiv = document.createElement('div');
    qualDiv.className = 'search-install-qualified';
    qualDiv.textContent = data.qualified_name || '';
    titleDiv.appendChild(nameDiv);
    titleDiv.appendChild(qualDiv);
    const verSpan = document.createElement('span');
    verSpan.className = 'search-install-version';
    verSpan.textContent = data.version || '';
    header.appendChild(iconSpan);
    header.appendChild(titleDiv);
    header.appendChild(verSpan);

    const lang = currentPageLanguage();

    const meta = document.createElement('div');
    meta.className = 'search-install-meta';
    if (data.summary) {
      const summaryDiv = document.createElement('div');
      summaryDiv.className = 'search-install-summary';
      summaryDiv.textContent = data.summary;
      meta.appendChild(summaryDiv);
    }
    const metaRows = [
      [uiText('search_install_audience', '受众'), formatAudienceType(data.audience_type)],
      [uiText('search_install_publisher', lang === 'en' ? 'Publisher / 发布者' : '发布者 / Publisher'), data.publisher || '-'],
      [uiText('search_install_install_scope', lang === 'en' ? 'Install Scope / 安装范围' : '安装范围 / Install Scope'), formatInstallScope(skill.install_scope || data.install_scope) || '-'],
      [uiText('search_install_listing_mode', lang === 'en' ? 'Listing Mode / 列出模式' : '列出模式 / Listing Mode'), formatListingMode(skill.listing_mode || data.listing_mode) || '-'],
      [uiText('search_install_runtime', lang === 'en' ? 'Runtime / 运行时' : '运行时 / Runtime'), (skill.runtime && skill.runtime.platform) || (data.runtime && data.runtime.platform) || '-'],
      [uiText('search_install_readiness', lang === 'en' ? 'Readiness / 就绪状态' : '就绪状态 / Readiness'), skill.runtime_readiness || data.runtime_readiness || '-'],
      [uiText('search_install_workspace_targets', lang === 'en' ? 'Workspace Targets / 工作区目标' : '工作区目标 / Workspace Targets'), (skill.workspace_targets || data.workspace_targets || []).join(', ') || '-'],
      [uiText('search_install_bundle_sha256', lang === 'en' ? 'Bundle SHA256 / 包 SHA256' : '包 SHA256 / Bundle SHA256'), data.bundle_sha256 || '-'],
    ];
    metaRows.forEach(([label, value]) => {
      const row = document.createElement('div');
      row.className = 'search-install-row';
      const lbl = document.createElement('span');
      lbl.className = 'search-install-label';
      lbl.textContent = label;
      const val = document.createElement('span');
      val.className = 'search-install-value';
      val.textContent = value;
      row.appendChild(lbl);
      row.appendChild(val);
      meta.appendChild(row);
    });

    const divider = document.createElement('div');
    divider.className = 'search-install-divider';

    const links = document.createElement('div');
    links.className = 'search-install-links';
    const artifacts = [
      { key: 'manifest', label: uiText('search_install_manifest', '清单'), url: data.manifest_url },
      { key: 'bundle', label: uiText('search_install_bundle', '包'), url: data.bundle_url },
      { key: 'provenance', label: uiText('search_install_provenance', '来源'), url: data.provenance_url },
      { key: 'signature', label: uiText('search_install_signature', '签名'), url: data.signature_url },
    ];
    artifacts.forEach(({ label, url }) => {
      if (url && isSafeUrl(url)) {
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.className = 'kawaii-button kawaii-button--ghost';
        link.classList.add('search-install-link');
        link.textContent = label;
        links.appendChild(link);
      }
    });

    const actions = document.createElement('div');
    actions.className = 'search-install-actions';
    const installRef = skill.install_ref || '';
    const installApiPath = skill.install_api_path || '';
    if (installRef) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'kawaii-button kawaii-button--secondary';
      btn.style.cssText = 'font-size:0.78rem;padding:0.45rem 0.9rem;';
      btn.dataset.copy = installRef;
      btn.textContent = uiText('search_install_copy_ref', '复制 install_ref');
      actions.appendChild(btn);
    }
    if (installApiPath) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'kawaii-button kawaii-button--ghost';
      btn.style.cssText = 'font-size:0.78rem;padding:0.45rem 0.9rem;';
      btn.dataset.copy = installApiPath;
      btn.textContent = uiText('search_install_copy_api', '复制 API 路径');
      actions.appendChild(btn);
    }
    if (data.bundle_url && isSafeUrl(data.bundle_url)) {
      const a = document.createElement('a');
      a.href = data.bundle_url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.className = 'kawaii-button kawaii-button--primary';
      a.style.cssText = 'font-size:0.78rem;padding:0.45rem 0.9rem;';
      a.textContent = uiText('search_install_open_artifact', '打开产物');
      actions.appendChild(a);
    }

    panel.appendChild(backBtn);
    panel.appendChild(header);
    panel.appendChild(meta);
    panel.appendChild(divider);
    panel.appendChild(links);
    panel.appendChild(actions);

    this.dropdown.appendChild(panel);
    bindCopyTriggers(this.dropdown);
    setTimeout(() => backBtn.focus(), 50);
  }

  selectNext() {
    const items = this.dropdown.querySelectorAll('.search-result');
    if (items.length === 0) return;

    this.selectedIndex = (this.selectedIndex + 1) % items.length;
    this.updateSelection(items);
  }

  selectPrev() {
    const items = this.dropdown.querySelectorAll('.search-result');
    if (items.length === 0) return;

    this.selectedIndex = this.selectedIndex <= 0 ? items.length - 1 : this.selectedIndex - 1;
    this.updateSelection(items);
  }

  updateSelection(items) {
    items.forEach((item, i) => {
      const isSelected = i === this.selectedIndex;
      item.classList.toggle('search-result--selected', isSelected);
      item.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      // Update input's aria-activedescendant for screen readers
      if (isSelected && this.input) {
        this.input.setAttribute('aria-activedescendant', item.id);
      }
    });

    const selected = items[this.selectedIndex];
    if (selected) {
      selected.scrollIntoView({ block: 'nearest' });
    }
  }

  activateSelected() {
    const items = this.dropdown.querySelectorAll('.search-result');
    const selected = items[this.selectedIndex];
    if (!selected) return;
    const copyText = selected.dataset.copy;
    if (copyText) {
      copyToClipboard(copyText);
    } else {
      selected.click();
    }
  }

  open() {
    if (this.dropdown) {
      this.dropdown.hidden = false;
      if (this.input) {
        this.input.setAttribute('aria-expanded', 'true');
      }
    }
  }

  close() {
    if (this.dropdown) {
      this.dropdown.hidden = true;
      if (this.input) {
        this.input.setAttribute('aria-expanded', 'false');
        this.input.removeAttribute('aria-activedescendant');
      }
    }
    this.selectedIndex = -1;
  }
}
