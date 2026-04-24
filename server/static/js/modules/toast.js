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
      this.container.setAttribute('aria-live', 'polite');
      this.container.setAttribute('aria-atomic', 'false');
      document.body.appendChild(this.container);
    }
    this.maxStack = 5;
  }

  show(message, type = 'info', duration = 3000) {
    // Enforce stack limit
    const toasts = this.container.querySelectorAll('.toast');
    if (toasts.length >= this.maxStack) {
      toasts[0].remove();
    }

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

    let autoTimer = null;
    let remaining = duration;
    let startTime = Date.now();

    const removeToast = () => {
      if (autoTimer) clearTimeout(autoTimer);
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        toast.remove();
      } else {
        toast.style.animation = 'toast-out 300ms ease forwards';
        setTimeout(() => toast.remove(), 300);
      }
    };

    closeBtn.addEventListener('click', removeToast);

    const startTimer = () => {
      startTime = Date.now();
      autoTimer = setTimeout(removeToast, remaining);
    };

    const pauseTimer = () => {
      if (autoTimer) {
        clearTimeout(autoTimer);
        autoTimer = null;
        remaining -= Date.now() - startTime;
        if (remaining < 0) remaining = 0;
      }
    };

    // Pause on hover / focus
    toast.addEventListener('mouseenter', pauseTimer);
    toast.addEventListener('mouseleave', startTimer);
    toast.addEventListener('focusin', pauseTimer);
    toast.addEventListener('focusout', startTimer);

    toast.appendChild(icon);
    toast.appendChild(content);
    toast.appendChild(closeBtn);

    this.container.appendChild(toast);
    startTimer();
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
