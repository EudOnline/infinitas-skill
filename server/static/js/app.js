/**
 * infinitas-skill v2 - Core JavaScript
 */

const APP_UI = window.APP_UI || {};

function currentPageLanguage() {
  const lang = (document.documentElement.lang || '').toLowerCase();
  return lang.startsWith('en') ? 'en' : 'zh';
}

function uiText(key, fallback) {
  const value = APP_UI[key];
  return typeof value === 'string' && value ? value : fallback;
}

function uiTemplate(key, fallback, replacements = {}) {
  let template = uiText(key, fallback);
  Object.entries(replacements).forEach(([name, value]) => {
    template = template.replace(`{${name}}`, String(value));
  });
  return template;
}

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
  }

  show(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    
    const icon = document.createElement('span');
    icon.className = 'toast__icon';
    icon.textContent = this.getIcon(type);
    
    const content = document.createElement('span');
    content.className = 'toast__content';
    content.textContent = message;
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast__close';
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', () => toast.remove());
    
    toast.appendChild(icon);
    toast.appendChild(content);
    toast.appendChild(closeBtn);

    this.container.appendChild(toast);

    // Auto remove
    setTimeout(() => {
      toast.style.animation = 'toast-out 300ms ease forwards';
      setTimeout(() => toast.remove(), 300);
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
      
      // Escape to close
      if (e.key === 'Escape') {
        this.close();
      }
      
      // Arrow navigation
      if (this.dropdown && !this.dropdown.hidden) {
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
        `/api/search?q=${encodeURIComponent(query)}&lang=${encodeURIComponent(currentPageLanguage())}`,
        { signal: this.abortController.signal }
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
        toast.info(uiText('search_auth_required', '请先登录后搜索私有目录'));
        if (typeof window.openAuthModal === 'function') {
          window.openAuthModal();
        }
        return;
      }
      
      console.error('Search error:', err);
      this.renderFallback(query);
    }
  }

  render(data) {
    if (!this.dropdown) return;
    
    // Clear previous content and reset ARIA
    this.dropdown.innerHTML = '';
    this.dropdown.setAttribute('role', 'listbox');
    this.dropdown.setAttribute('aria-label', uiText('search_results_label', '搜索结果'));
    
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
        const inspectTarget = skill.qualified_name || skill.id || skill.name || '';
        const inspectCommand = inspectTarget ? `scripts/inspect-skill.sh ${inspectTarget}` : '';
        el.type = 'button';
        el.className = 'search-result';
        el.setAttribute('role', 'option');
        el.setAttribute('id', `search-option-${i}`);
        el.setAttribute('aria-selected', 'false');
        el.setAttribute('tabindex', '-1');
        el.dataset.index = i;
        if (inspectCommand) {
          el.dataset.copy = inspectCommand;
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
        const el = document.createElement('div');
        el.className = 'search-result';
        el.setAttribute('role', 'option');
        el.setAttribute('id', `search-option-${skillsOffset + i}`);
        el.setAttribute('aria-selected', 'false');
        el.setAttribute('tabindex', '-1');
        el.dataset.index = skillsOffset + i;
        el.style.cursor = 'pointer';
        
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
        el.addEventListener('click', () => copyToClipboard(cmd.command));
        
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
      trigger.style.cssText = 'font-size: 0.85rem; padding: 0.5rem 1rem;';
      trigger.dataset.copy = uiText('search_create_command', 'scripts/new-skill.sh lvxiaoer/my-skill basic');
      trigger.textContent = uiText('search_create_label', '创建新技能');
      
      empty.appendChild(icon);
      empty.appendChild(text);
      empty.appendChild(trigger);
      
      this.dropdown.appendChild(empty);
    }

    bindCopyTriggers(this.dropdown);
    
    this.selectedIndex = -1;
  }

  renderFallback(query) {
    // Show static skills from page data
    const skills = window.SKILLS_DATA || [];
    const filtered = skills.filter(s => 
      s.name.toLowerCase().includes(query.toLowerCase()) ||
      s.summary?.toLowerCase().includes(query.toLowerCase())
    );
    
    this.render({ skills: filtered.slice(0, 5), commands: [] });
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
    if (selected) {
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
    textarea.select();
    
    try {
      document.execCommand('copy');
      toast.success(document.body.dataset.copySuccess || uiText('copy_success', '已复制'));
    } catch (err) {
      toast.error(document.body.dataset.copyError || uiText('copy_error', '复制失败'));
    }
    
    document.body.removeChild(textarea);
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

async function useSkill(skillId) {
  try {
    const response = await fetch(`/api/skills/${skillId}/use`, { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) throw new Error('Failed');
    
    const data = await response.json();
    
    // Copy command to clipboard
    await copyToClipboard(data.command);
    
    toast.success(uiTemplate('use_skill_ready', '技能 {name} 已就绪，命令已复制', { name: data.skill.name }));
  } catch (err) {
    toast.error(uiText('use_skill_error', '使用技能失败，请重试'));
    console.error(err);
  }
}

function toggleTheme() {
  window.themeManager.toggle();
}

function setTheme(theme) {
  window.themeManager.set(theme);
}

// ============================================
// Error Handling
// ============================================
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  if (window.toast) {
    toast.error(uiText('generic_action_failed', '操作失败，请刷新页面重试'));
  }
});

window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
  if (window.toast) {
    toast.error(uiText('generic_unexpected_error', '发生错误，请刷新页面重试'));
  }
});

// ============================================
// Initialize
// ============================================
document.addEventListener('DOMContentLoaded', () => {
  bindCopyTriggers();

  // Initialize search
  try {
    window.searchManager = new SearchManager();
  } catch (err) {
    console.error('Failed to initialize search:', err);
  }

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
        const delay = el.style.getPropertyValue('--reveal-index');
        if (delay) {
          el.style.transitionDelay = `${parseInt(delay) * 100}ms`;
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

// Cleanup on page unload (for SPA or navigation scenarios)
window.addEventListener('beforeunload', () => {
  if (window.searchManager) {
    window.searchManager.destroy();
  }
  
  // Clean up Intersection Observer
  if (window._revealObserver) {
    window._revealObserver.disconnect();
    window._revealObserver = null;
  }
});

// Expose globals for inline handlers
window.copyToClipboard = copyToClipboard;
window.useSkill = useSkill;
window.toggleTheme = toggleTheme;
window.setTheme = setTheme;
