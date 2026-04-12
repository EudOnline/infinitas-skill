/**
 * infinitas-skill v2 - Core JavaScript
 */

function parseJsonData(id) {
  try {
    const el = document.getElementById(id);
    return el && el.dataset.json ? JSON.parse(el.dataset.json) : {};
  } catch (_) {
    return {};
  }
}
const APP_UI = parseJsonData('app-ui-data');
const APP_SESSION = parseJsonData('app-session-data');
const APP_AUTH_CONFIG = parseJsonData('app-auth-config-data');
const HOME_AUTH_SESSION_CONFIG = parseJsonData('home-auth-session-data');

window.APP_UI = APP_UI;
window.APP_SESSION = APP_SESSION;
window.AUTH_SESSION_CONFIG = {
  ...APP_AUTH_CONFIG,
  ...HOME_AUTH_SESSION_CONFIG,
};

function currentPageLanguage() {
  const lang = (document.documentElement.lang || '').toLowerCase();
  return lang.startsWith('en') ? 'en' : 'zh';
}

function currentSearchScope() {
  if (document.body?.classList.contains('page-console')) {
    return 'me';
  }
  return 'public';
}

function uiText(key, fallback) {
  const value = APP_UI[key];
  return typeof value === 'string' && value ? value : fallback;
}

function isSafeUrl(url) {
  return typeof url === 'string' && /^https?:\/\//.test(url);
}

function sanitizeClassName(text) {
  return String(text || '').trim().replace(/\s+/g, '-').replace(/[^a-zA-Z0-9_-]/g, '');
}

function uiTemplate(key, fallback, replacements = {}) {
  let template = uiText(key, fallback);
  Object.entries(replacements).forEach(([name, value]) => {
    template = template.replaceAll(`{${name}}`, String(value));
  });
  return template;
}

window.infinitasAppShell = {
  currentPageLanguage,
  currentSearchScope,
  uiText,
  uiTemplate,
};

// ============================================
// Toast Notification System
// ============================================
class ToastManager {
  constructor() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
    this.container.setAttribute('aria-live', 'polite');
    this.container.setAttribute('aria-atomic', 'false');
  }

  show(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    
    const icon = document.createElement('span');
    icon.className = 'toast__icon';
    icon.textContent = this.getIcon(type);
    
    const content = document.createElement('span');
    content.className = 'toast__content';
    content.textContent = message;
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast__close';
    closeBtn.setAttribute('type', 'button');
    closeBtn.setAttribute('aria-label', uiText('toast_close', 'Dismiss notification'));
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', () => {
      if (toast._autoTimer) clearTimeout(toast._autoTimer);
      toast.remove();
    });

    toast.appendChild(icon);
    toast.appendChild(content);
    toast.appendChild(closeBtn);

    this.container.appendChild(toast);

    // Auto remove
    toast._autoTimer = setTimeout(() => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        toast.remove();
      } else {
        toast.style.animation = 'toast-out 300ms ease forwards';
        setTimeout(() => toast.remove(), 300);
      }
    }, duration);
  }

  getIcon(type) {
    const icons = {
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️'
    };
    return icons[type] || icons.info;
  }

  success(message, duration) { this.show(message, 'success', duration); }
  error(message, duration) { this.show(message, 'error', duration); }
  warning(message, duration) { this.show(message, 'warning', duration); }
  info(message, duration) { this.show(message, 'info', duration); }
}

// Global toast instance
window.toast = new ToastManager();

// ============================================
// Theme Manager
// ============================================
class ThemeManager {
  constructor() {
    const storageKey = 'kawaii-color-scheme';
    this.storageKey = storageKey;
    this.systemPreference = window.matchMedia('(prefers-color-scheme: dark)');
    this.current = this.resolveInitialScheme();
    this.init();
  }

  resolveInitialScheme() {
    const html = document.documentElement;
    const fromDom = html.dataset.colorScheme;
    if (fromDom === 'light' || fromDom === 'dark') {
      return fromDom;
    }

    try {
      const stored = window.localStorage.getItem(this.storageKey);
      if (stored === 'light' || stored === 'dark') {
        return stored;
      }
    } catch (_err) {
      // Ignore storage access failures and fall back to system preference.
    }

    return this.systemPreference.matches ? 'dark' : 'light';
  }

  updateButtons(scheme) {
    document.querySelectorAll('[data-theme-choice]').forEach((button) => {
      const active = button.dataset.themeChoice === scheme;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  init() {
    this.apply(this.current, false);
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-theme-choice]');
      if (btn) {
        this.set(btn.dataset.themeChoice);
      }
    });
  }

  apply(scheme, save = true) {
    const html = document.documentElement;
    scheme = scheme === 'dark' ? 'dark' : 'light';
    html.dataset.colorScheme = scheme;
    html.style.colorScheme = scheme;
    this.updateButtons(scheme);
    this.current = scheme;

    if (save) {
      try {
        window.localStorage.setItem(this.storageKey, scheme);
      } catch (_err) {
        // Ignore storage failures so the toggle still works for the session.
      }
    }
  }

  toggle() {
    const currentScheme = document.documentElement.dataset.colorScheme === 'dark' ? 'dark' : 'light';
    const next = currentScheme === 'dark' ? 'light' : 'dark';
    this.apply(next);
    toast.success(uiTemplate('theme_switched', '已切换到 {theme}', { theme: this.getThemeName(next) }));
  }

  set(scheme) {
    if (scheme === 'light' || scheme === 'dark') {
      this.apply(scheme);
    }
  }

  getThemeName(scheme) {
    const names = {
      light: uiText('theme_light_name', '浅色主题'),
      dark: uiText('theme_dark_name', '深色主题'),
    };
    return names[scheme] || scheme;
  }
}

// Global theme instance
window.themeManager = new ThemeManager();

// ============================================
// Search Manager
// ============================================
class SearchManager {
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
        toast.info(uiText('search_auth_required', '请先登录后搜索私人技能库'));
        if (typeof window.openConsoleAuthModal === 'function') {
          window.openConsoleAuthModal();
        } else if (typeof window.openHomeAuthModal === 'function') {
          window.openHomeAuthModal();
        }
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
        if (skill.install_api_path) {
          el.addEventListener('click', () => this.showSkillInstall(skill));
        } else {
          const inspectTarget = skill.qualified_name || skill.id || skill.name || '';
          const inspectCommand = inspectTarget ? `scripts/inspect-skill.sh ${inspectTarget}` : '';
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
      toast.error(err.message || uiText('generic_action_failed', '操作失败，请刷新页面重试'));
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

// ============================================
// Utility Functions
// ============================================

async function copyToClipboard(text) {
  if (!text) {
    toast.error(document.body.dataset.copyError || uiText('copy_error', '复制失败'));
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    toast.success(document.body.dataset.copySuccess || uiText('copy_success', '已复制'));
  } catch (err) {
    // Fallback
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    try {
      textarea.select();
      document.execCommand('copy');
      toast.success(document.body.dataset.copySuccess || uiText('copy_success', '已复制'));
    } catch (err) {
      toast.error(document.body.dataset.copyError || uiText('copy_error', '复制失败'));
    } finally {
      document.body.removeChild(textarea);
    }
  }
}

function bindCopyTriggers(root = document) {
  if (!root || typeof root.querySelectorAll !== 'function') {
    return;
  }

  root.querySelectorAll('[data-copy]').forEach((trigger) => {
    if (trigger.dataset.copyBound === 'true') {
      return;
    }
    trigger.dataset.copyBound = 'true';
    trigger.addEventListener('click', () => copyToClipboard(trigger.dataset.copy || ''));
  });
}

// ============================================
// Lifecycle Mutation Plumbing
// ============================================

async function apiGet(url, signal) {
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'same-origin',
    signal,
  });
  if (!response.ok) {
    const err = await parseApiError(response);
    throw err;
  }
  return response.json();
}

async function apiPost(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await parseApiError(response);
    throw err;
  }
  return response.json();
}

async function apiPatch(url, body) {
  const response = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await parseApiError(response);
    throw err;
  }
  return response.json();
}

async function parseApiError(response) {
  let message = '';
  try {
    const data = await response.json();
    message = data.detail || data.message || JSON.stringify(data);
  } catch (_e) {
    message = response.statusText || `HTTP ${response.status}`;
  }
  const err = new Error(message);
  err.status = response.status;
  return err;
}

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

function reloadWithToast(type, message, delay = 600) {
  const key = `lifecycle_toast_${Date.now()}`;
  try {
    sessionStorage.setItem(key, JSON.stringify({ type, message, ts: Date.now() }));
  } catch (_e) {}
  setTimeout(() => { window.location.href = preserveLang(window.location.pathname + window.location.search); }, delay);
}

function drainPendingToasts() {
  try {
    const keys = Object.keys(sessionStorage).filter(k => k.startsWith('lifecycle_toast_'));
    keys.forEach((key) => {
      const raw = sessionStorage.getItem(key);
      sessionStorage.removeItem(key);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data && data.type && data.message && window.toast) {
        window.toast.show(data.message, data.type, 4000);
      }
    });
  } catch (_e) {}
}

function preserveLang(path) {
  const lang = currentPageLanguage();
  if (!lang) return path;
  const url = new URL(path, window.location.origin);
  url.searchParams.set('lang', lang);
  return url.pathname + url.search;
}

// ============================================
// Lifecycle Actions
// ============================================

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
    toast.success(uiText('skill_created', '技能创建成功'));
    window.location.href = preserveLang(`/skills/${result.id}`);
  } catch (err) {
    setButtonLoading(button, false);
    toast.error(err.message || uiText('skill_create_error', '创建技能失败'));
  }
}

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
      toast.error(uiText('invalid_json', 'JSON 格式错误'));
      setButtonLoading(button, false);
      return;
    }
    const result = await apiPost(`/api/v1/skills/${encodeURIComponent(skillId)}/drafts`, data);
    toast.success(uiText('draft_created', '草稿创建成功'));
    window.location.href = preserveLang(`/drafts/${result.id}`);
  } catch (err) {
    setButtonLoading(button, false);
    toast.error(err.message || uiText('draft_create_error', '创建草稿失败'));
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
      toast.error(uiText('invalid_json', 'JSON 格式错误'));
      setButtonLoading(button, false);
      return;
    }
    await apiPatch(`/api/v1/drafts/${encodeURIComponent(draftId)}`, data);
    reloadWithToast('success', uiText('draft_saved', '草稿保存成功'));
  } catch (err) {
    setButtonLoading(button, false);
    toast.error(err.message || uiText('draft_save_error', '保存草稿失败'));
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
    toast.error(err.message || uiText('draft_seal_error', '封版失败'));
  }
}

async function createRelease(versionId, button) {
  setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/versions/${encodeURIComponent(versionId)}/releases`, {});
    reloadWithToast('success', uiText('release_created', '发布创建成功'));
  } catch (err) {
    setButtonLoading(button, false);
    toast.error(err.message || uiText('release_create_error', '创建发布失败'));
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
        toast.success(uiText('release_is_ready', '发布产物已就绪'));
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
        toast.error(err.message || uiText('generic_action_failed', '操作失败，请刷新页面重试'));
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
    toast.error(err.message || uiText('exposure_create_error', '创建分享出口失败'));
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
    toast.error(err.message || uiText('exposure_patch_error', '更新分享设置失败'));
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
    toast.error(err.message || uiText('exposure_activate_error', '激活分享失败'));
  }
}

async function revokeExposure(exposureId, button) {
  setButtonLoading(button, true);
  try {
    await apiPost(`/api/v1/exposures/${encodeURIComponent(exposureId)}/revoke`, {});
    reloadWithToast('success', uiText('exposure_revoked', '分享已撤销'));
  } catch (err) {
    setButtonLoading(button, false);
    toast.error(err.message || uiText('exposure_revoke_error', '撤销分享失败'));
  }
}

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
    toast.error(err.message || uiText('review_decision_error', '提交审核决定失败'));
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
    toast.error(err.message || uiText('review_detail_error', '加载详情失败'));
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

function formatAudienceType(audienceType) {
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

function formatInstallScope(scope) {
  const lang = currentPageLanguage();
  const map = {
    public: { zh: '公开', en: 'Public' },
    me: { zh: '仅自己', en: 'Only me' },
    grant: { zh: '授权', en: 'Grant' },
  };
  const entry = map[String(scope || '').toLowerCase()];
  return entry ? entry[lang] || entry.zh : (scope || '');
}

function formatListingMode(mode) {
  const lang = currentPageLanguage();
  const map = {
    listed: { zh: '已列出', en: 'Listed' },
    direct_only: { zh: '仅直链', en: 'Direct only' },
  };
  const entry = map[String(mode || '').toLowerCase()];
  return entry ? entry[lang] || entry.zh : (mode || '');
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

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
    toast.error(err.message || uiText('access_check_error', lang === 'en' ? 'Check failed / 检查失败' : '检查失败 / Check failed'));
  }
}

// ============================================
// Page Initializers
// ============================================

function initCreateSkill() {
  const form = document.getElementById('create-skill-form');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    createSkill(form);
  });
}

function initCreateDraft() {
  const form = document.getElementById('create-draft-form');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    createDraft(form);
  });
}

function initDraftDetail() {
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

function handleCreateReleaseClick(e) {
  const btn = e.target.closest('[data-action="create-release"]');
  if (!btn) return;
  const versionId = btn.dataset.versionId;
  if (versionId) createRelease(versionId, btn);
}

function initReleaseDetail() {
  const statusEl = document.getElementById('release-status');
  const releaseId = statusEl?.dataset.releaseId;
  if (statusEl && releaseId && statusEl.dataset.state === 'preparing') {
    window._releasePollStop = pollReleaseReady(releaseId);
  }
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
  }
}

function handleShareDetailSubmit(e) {
  const form = e.target.closest('[data-action="patch-exposure"]');
  if (!form) return;
  e.preventDefault();
  patchExposure(form.dataset.exposureId, form);
}

function initShareDetail() {
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

function handleReviewCaseClick(e) {
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

function initAccessTokens() {
  checkAccessMe();
  // click handler registered by initDelegatedActions
}

// Unified delegated action dispatcher (single click + submit listener)
function initDelegatedActions() {
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

// ============================================
// Error Handling
// ============================================
(function setupErrorHandlers() {
  let lastErrorTime = 0;
  const minInterval = 5000;

  window.addEventListener('unhandledrejection', (event) => {
    if (typeof event.reason?.stack === 'string' && !event.reason.stack.includes(window.location.origin)) return;
    const now = Date.now();
    if (now - lastErrorTime < minInterval) return;
    lastErrorTime = now;
    console.error('Unhandled promise rejection:', event.reason);
    if (window.toast) {
      window.toast.error(uiText('generic_unexpected_error', '发生错误，请刷新页面重试'));
    }
  });

  window.addEventListener('error', (event) => {
    if (typeof event.filename === 'string' && !event.filename.includes(window.location.origin)) return;
    const now = Date.now();
    if (now - lastErrorTime < minInterval) return;
    lastErrorTime = now;
    console.error('Global error:', event.error);
    if (window.toast) {
      window.toast.error(uiText('generic_unexpected_error', '发生错误，请刷新页面重试'));
    }
  });
})();

// ============================================
// Initialize
// ============================================
document.addEventListener('DOMContentLoaded', () => {
  bindCopyTriggers();
  drainPendingToasts();

  // Initialize search
  try {
    window.searchManager = new SearchManager();
  } catch (err) {
    console.error('Failed to initialize search:', err);
  }

  // Initialize lifecycle action pages
  initDelegatedActions();
  initCreateSkill();
  initCreateDraft();
  initDraftDetail();
  initReleaseDetail();
  initShareDetail();
  initAccessTokens();

  // Animate elements on scroll using Intersection Observer (better performance)
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  
  if (!prefersReducedMotion.matches && 'IntersectionObserver' in window) {
    const revealElements = document.querySelectorAll('[data-reveal]');
    
    if (revealElements.length > 0) {
      // Set initial state for reveal elements
      revealElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(14px)';
        el.style.transition = `opacity 520ms var(--ease-out-gentle), transform 520ms var(--ease-out-gentle)`;
        // Apply stagger delay if specified
        const delay = getComputedStyle(el).getPropertyValue('--reveal-index');
        if (delay) {
          el.style.transitionDelay = `${parseInt(delay, 10) * 100}ms`;
        }
      });
      
      // Use Intersection Observer for better performance
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            // Stop observing once animated
            observer.unobserve(entry.target);
          }
        });
      }, {
        threshold: 0.1,
        rootMargin: '0px 0px -10% 0px'
      });
      
      revealElements.forEach(el => observer.observe(el));
      
      // Store for cleanup
      window._revealObserver = observer;
    }
  }
});


// Expose globals for inline handlers
