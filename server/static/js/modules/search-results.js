import { currentSearchScope, sanitizeClassName, uiText } from './config.js';
import { bindCopyTriggers } from './api.js';

function resultButton(index) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'search-result';
  button.setAttribute('role', 'option');
  button.setAttribute('id', `search-option-${index}`);
  button.setAttribute('aria-selected', 'false');
  button.setAttribute('tabindex', '-1');
  button.dataset.index = index;
  return button;
}

function resultInfo(nameText, description, descriptionClass = 'search-result__desc') {
  const info = document.createElement('div');
  info.className = 'search-result__info';
  const name = document.createElement('div');
  name.className = 'search-result__name';
  name.textContent = nameText;
  const detail = document.createElement('div');
  detail.className = descriptionClass;
  detail.textContent = description;
  info.append(name, detail);
  return info;
}

function skillMeta(skill) {
  const meta = document.createElement('div');
  meta.className = 'search-result__meta';
  for (const [value, className] of [
    [skill.runtime_readiness, `search-result__readiness search-result__readiness--${sanitizeClassName(skill.runtime_readiness)}`],
    [skill.runtime?.platform, 'search-result__platform'],
    [skill.workspace_targets?.join(', '), 'search-result__targets'],
  ]) {
    if (!value) continue;
    const item = document.createElement('span');
    item.className = className;
    item.textContent = value;
    meta.appendChild(item);
  }
  return meta;
}

function skillButton(skill, index, showSkillInstall) {
  const button = resultButton(index);
  if (skill.install_api_path && currentSearchScope() !== 'public') {
    button.addEventListener('click', () => showSkillInstall(skill));
  } else {
    const target = skill.qualified_name || skill.id || skill.name || '';
    if (target) button.dataset.copy = `uv run infinitas discovery inspect ${target} --json`;
  }
  const icon = document.createElement('span');
  icon.className = 'search-result__icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = skill.icon || '🎯';
  const info = resultInfo(skill.name, skill.summary || '');
  const meta = skillMeta(skill);
  if (meta.hasChildNodes()) info.appendChild(meta);
  const badge = document.createElement('span');
  badge.className = 'search-result__badge';
  badge.textContent = skill.version || '';
  button.append(icon, info, badge);
  return button;
}

function commandButton(command, index) {
  const button = resultButton(index);
  button.classList.add('cursor-pointer');
  button.dataset.copy = command.command;
  const icon = document.createElement('span');
  icon.className = 'search-result__icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = '⌨️';
  button.append(icon, resultInfo(command.name, command.command, 'search-result__code'));
  return button;
}

function section(label, buttons) {
  if (!buttons.length) return null;
  const container = document.createElement('div');
  container.className = 'search-dropdown__section';
  container.setAttribute('role', 'group');
  container.setAttribute('aria-label', label);
  const heading = document.createElement('h4');
  heading.textContent = label;
  heading.setAttribute('aria-hidden', 'true');
  const results = document.createElement('div');
  results.className = 'search-results';
  results.setAttribute('role', 'presentation');
  results.append(...buttons);
  container.append(heading, results);
  return container;
}

function emptyState() {
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
  const action = document.createElement('button');
  action.type = 'button';
  action.className = 'kawaii-button kawaii-button--primary search-empty-action';
  action.dataset.copy = uiText('search_create_command', 'scripts/new-skill.sh publisher/my-skill basic');
  action.textContent = uiText('search_create_label', '创建新技能');
  empty.append(icon, text, action);
  return empty;
}

export function renderSearchResults(dropdown, data, showSkillInstall) {
  dropdown.replaceChildren();
  dropdown.setAttribute('role', 'listbox');
  dropdown.setAttribute('aria-label', uiText('search_results_label', '搜索结果'));
  const skills = (data.skills || []).map((skill, index) => skillButton(skill, index, showSkillInstall));
  const offset = skills.length;
  const commands = (data.commands || []).map((command, index) => commandButton(command, offset + index));
  const sections = [
    section(uiText('search_skills_label', '技能'), skills),
    section(uiText('search_commands_label', '命令'), commands),
  ].filter(Boolean);
  dropdown.append(...(sections.length ? sections : [emptyState()]));
  bindCopyTriggers(dropdown);
}
