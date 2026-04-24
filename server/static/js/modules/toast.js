/**
 * Toast notification system
 */
import { uiText } from './config.js';

export class ToastManager {
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
