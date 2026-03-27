/**
 * infinitas-skill v2 - Core JavaScript
 */

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
    toast.innerHTML = `
      <span class="toast__icon">${this.getIcon(type)}</span>
      <span class="toast__content">${message}</span>
      <button class="toast__close" onclick="this.parentElement.remove()">×</button>
    `;

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
    toast.success(`已切换到 ${this.getThemeName(next)}`);
  }

  set(scheme) {
    if (scheme === 'light' || scheme === 'dark') {
      this.apply(scheme);
    }
  }

  getThemeName(scheme) {
    const names = {
      light: '浅色主题',
      dark: '深色主题',
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
    
    if (this.input) {
      this.init();
    }
  }

  init() {
    // Input handling
    this.input.addEventListener('input', (e) => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => {
        this.search(e.target.value);
      }, 150);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
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
    });

    // Click outside to close
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.search-bar-wrapper')) {
        this.close();
      }
    });
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
        `/api/search?q=${encodeURIComponent(query)}`,
        { signal: this.abortController.signal }
      );
      
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
      
      console.error('Search error:', err);
      this.renderFallback(query);
    }
  }

  render(data) {
    if (!this.dropdown) return;
    
    // Clear previous content
    this.dropdown.innerHTML = '';
    
    // Skills section
    if (data.skills && data.skills.length > 0) {
      const section = document.createElement('div');
      section.className = 'search-dropdown__section';
      section.innerHTML = '<h4>技能</h4>';
      
      const results = document.createElement('div');
      results.className = 'search-results';
      
      data.skills.forEach((skill, i) => {
        const el = document.createElement('a');
        el.href = `/skills/${encodeURIComponent(skill.id)}`;
        el.className = 'search-result';
        el.dataset.index = i;
        
        el.innerHTML = `
          <span class="search-result__icon" aria-hidden="true">${skill.icon || '🎯'}</span>
          <div class="search-result__info">
            <div class="search-result__name"></div>
            <div class="search-result__desc"></div>
          </div>
          <span class="search-result__badge"></span>
        `;
        
        // Use textContent to prevent XSS
        el.querySelector('.search-result__name').textContent = skill.name;
        el.querySelector('.search-result__desc').textContent = skill.summary || '';
        el.querySelector('.search-result__badge').textContent = skill.version || '';
        
        results.appendChild(el);
      });
      
      section.appendChild(results);
      this.dropdown.appendChild(section);
    }
    
    // Commands section
    if (data.commands && data.commands.length > 0) {
      const section = document.createElement('div');
      section.className = 'search-dropdown__section';
      section.innerHTML = '<h4>命令</h4>';
      
      const results = document.createElement('div');
      results.className = 'search-results';
      
      data.commands.forEach((cmd, i) => {
        const el = document.createElement('div');
        el.className = 'search-result';
        el.dataset.index = i + (data.skills?.length || 0);
        el.style.cursor = 'pointer';
        
        el.innerHTML = `
          <span class="search-result__icon" aria-hidden="true">⌨️</span>
          <div class="search-result__info">
            <div class="search-result__name"></div>
            <code class="search-result__code"></code>
          </div>
        `;
        
        // Use textContent to prevent XSS
        el.querySelector('.search-result__name').textContent = cmd.name;
        el.querySelector('.search-result__code').textContent = cmd.command;
        
        // Safely bind click event
        el.addEventListener('click', () => copyToClipboard(cmd.command));
        
        results.appendChild(el);
      });
      
      section.appendChild(results);
      this.dropdown.appendChild(section);
    }
    
    // Empty state
    if (!this.dropdown.hasChildNodes()) {
      this.dropdown.innerHTML = `
        <div class="search-empty">
          <div class="search-empty__icon" aria-hidden="true">🔍</div>
          <p>未找到匹配结果</p>
          <a href="/console/new-skill" class="kawaii-button kawaii-button--primary" style="font-size: 0.85rem; padding: 0.5rem 1rem;">创建新技能</a>
        </div>
      `;
    }
    
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
      item.classList.toggle('search-result--selected', i === this.selectedIndex);
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
    }
  }

  close() {
    if (this.dropdown) {
      this.dropdown.hidden = true;
    }
    this.selectedIndex = -1;
  }
}

// ============================================
// Utility Functions
// ============================================

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success('已复制到剪贴板');
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
      toast.success('已复制到剪贴板');
    } catch (err) {
      toast.error('复制失败');
    }
    
    document.body.removeChild(textarea);
  }
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
    
    toast.success(`技能 ${data.skill.name} 已就绪，命令已复制`);
  } catch (err) {
    toast.error('使用技能失败，请重试');
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
    toast.error('操作失败，请刷新页面重试');
  }
});

window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
  if (window.toast) {
    toast.error('发生错误，请刷新页面重试');
  }
});

// ============================================
// Initialize
// ============================================
document.addEventListener('DOMContentLoaded', () => {
  // Initialize search
  try {
    window.searchManager = new SearchManager();
  } catch (err) {
    console.error('Failed to initialize search:', err);
  }

  // Animate elements on scroll (throttled)
  let ticking = false;
  const animateOnScroll = () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        document.querySelectorAll('[data-animate]').forEach(el => {
          const rect = el.getBoundingClientRect();
          if (rect.top < window.innerHeight * 0.9) {
            el.classList.add('animate-fadeInUp');
          }
        });
        ticking = false;
      });
      ticking = true;
    }
  };
  
  window.addEventListener('scroll', animateOnScroll, { passive: true });
  animateOnScroll(); // Initial check
});

// Expose globals for inline handlers
window.copyToClipboard = copyToClipboard;
window.useSkill = useSkill;
window.toggleTheme = toggleTheme;
window.setTheme = setTheme;
