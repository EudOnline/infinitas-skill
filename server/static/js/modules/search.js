/** Global skill and command search coordinator. */

import { currentPageLanguage, currentSearchScope, logError, uiText } from './config.js';
import { copyToClipboard, apiGet } from './api.js';
import { renderInstallPanel } from './search-install-panel.js';
import { renderSearchResults } from './search-results.js';

export {
  formatAudienceType,
  formatInstallScope,
  formatListingMode,
} from './search-formatting.js';

let toastRef = null;

export function setSearchToastRef(ref) {
  toastRef = ref;
}

export class SearchManager {
  constructor() {
    this.input = document.getElementById('global-search');
    this.dropdown = document.getElementById('search-dropdown');
    this.debounceTimer = null;
    this.selectedIndex = -1;
    this.searchId = 0;
    this.abortController = null;
    this.handlers = {};
    this.lastSearchData = null;
    if (this.input) this.init();
  }

  init() {
    this.handlers.input = (event) => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.search(event.target.value), 250);
    };
    this.handlers.keydown = (event) => this.handleKeyDown(event);
    this.handlers.click = (event) => {
      if (!event.target.closest('.search-bar-wrapper')) this.close();
    };
    this.input.addEventListener('input', this.handlers.input);
    document.addEventListener('keydown', this.handlers.keydown);
    document.addEventListener('click', this.handlers.click);
  }

  handleKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
      event.preventDefault();
      this.input.focus();
    }
    if (event.key === 'Escape') {
      if (this.dropdown?.getAttribute('role') === 'dialog' && this.lastSearchData) {
        this.showLastResults();
        return;
      }
      this.close();
    }
    if (!this.dropdown || this.dropdown.hidden || this.isEditingOtherField()) return;
    const action = {
      ArrowDown: () => this.selectNext(),
      ArrowUp: () => this.selectPrev(),
      Enter: () => this.activateSelected(),
    }[event.key];
    if (action) {
      event.preventDefault();
      action();
    }
  }

  isEditingOtherField() {
    const active = document.activeElement;
    return active !== this.input && ['INPUT', 'TEXTAREA', 'SELECT'].includes(active?.tagName);
  }

  destroy() {
    this.input?.removeEventListener('input', this.handlers.input);
    document.removeEventListener('keydown', this.handlers.keydown);
    document.removeEventListener('click', this.handlers.click);
    clearTimeout(this.debounceTimer);
    this.abortController?.abort();
  }

  async fetchResults(query, searchId) {
    const response = await fetch(
      `/api/v1/search?q=${encodeURIComponent(query)}&lang=${encodeURIComponent(currentPageLanguage())}&scope=${encodeURIComponent(currentSearchScope())}`,
      { credentials: 'same-origin', signal: this.abortController.signal },
    );
    if (response.status === 401) {
      const error = new Error('Search requires authentication');
      error.code = 'SEARCH_AUTH_REQUIRED';
      throw error;
    }
    if (searchId !== this.searchId) return null;
    if (!response.ok) throw new Error('Search failed');
    const data = await response.json();
    return searchId === this.searchId ? data : null;
  }

  async search(query) {
    if (!query.trim()) {
      this.close();
      return;
    }
    this.abortController?.abort();
    this.abortController = new AbortController();
    const searchId = ++this.searchId;
    try {
      const data = await this.fetchResults(query, searchId);
      if (!data) return;
      this.render(data);
      this.open();
    } catch (error) {
      if (error.name === 'AbortError' || searchId !== this.searchId) return;
      if (error.code === 'SEARCH_AUTH_REQUIRED') {
        this.close();
        toastRef?.info(uiText('search_auth_required', '请先登录后搜索私人技能库'));
        document.dispatchEvent(new CustomEvent('infinitas:auth-required'));
        return;
      }
      logError('Search error:', error);
      this.render({ skills: [], commands: [] });
    }
  }

  render(data) {
    if (!this.dropdown) return;
    this.lastSearchData = data;
    this.input?.removeAttribute('aria-activedescendant');
    renderSearchResults(this.dropdown, data, (skill) => this.showSkillInstall(skill));
    this.selectedIndex = -1;
  }

  async showSkillInstall(skill) {
    if (!skill.install_api_path) return;
    try {
      const data = await apiGet(skill.install_api_path);
      renderInstallPanel(this.dropdown, data, skill, () => this.showLastResults());
    } catch (error) {
      toastRef?.error(error.message || uiText('generic_action_failed', '操作失败，请刷新页面重试'));
    }
  }

  showLastResults() {
    if (!this.lastSearchData) {
      this.close();
      return;
    }
    this.render(this.lastSearchData);
    this.open();
    if (!window.matchMedia('(pointer: coarse)').matches) this.input?.focus();
  }

  resultItems() {
    return this.dropdown?.querySelectorAll('.search-result') || [];
  }

  selectNext() {
    const items = this.resultItems();
    if (!items.length) return;
    this.selectedIndex = (this.selectedIndex + 1) % items.length;
    this.updateSelection(items);
  }

  selectPrev() {
    const items = this.resultItems();
    if (!items.length) return;
    this.selectedIndex = this.selectedIndex <= 0 ? items.length - 1 : this.selectedIndex - 1;
    this.updateSelection(items);
  }

  updateSelection(items) {
    items.forEach((item, index) => {
      const selected = index === this.selectedIndex;
      item.classList.toggle('search-result--selected', selected);
      item.setAttribute('aria-selected', String(selected));
      if (selected) this.input?.setAttribute('aria-activedescendant', item.id);
    });
    items[this.selectedIndex]?.scrollIntoView({ block: 'nearest' });
  }

  activateSelected() {
    const selected = this.resultItems()[this.selectedIndex];
    if (!selected) return;
    if (selected.dataset.copy) copyToClipboard(selected.dataset.copy);
    else selected.click();
  }

  open() {
    if (!this.dropdown) return;
    this.dropdown.hidden = false;
    this.input?.setAttribute('aria-expanded', 'true');
  }

  close() {
    if (this.dropdown) this.dropdown.hidden = true;
    this.input?.setAttribute('aria-expanded', 'false');
    this.input?.removeAttribute('aria-activedescendant');
    this.selectedIndex = -1;
  }
}
