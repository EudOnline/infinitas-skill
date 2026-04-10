(() => {
  'use strict';

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReducedMotion) {
    return;
  }

  /* 🎀 浮动装饰动画样式 */
  const decoStyles = document.createElement('style');
  decoStyles.textContent = `
    .floating-decoration {
      position: fixed;
      font-size: 1.5rem;
      pointer-events: none;
      z-index: 1;
      opacity: 0.4;
    }
    .floating-heart {
      animation: float-around 12s ease-in-out infinite;
    }
    .floating-star {
      animation: float-around 15s ease-in-out infinite reverse;
    }
    .floating-sparkle {
      animation: sparkle-float 8s ease-in-out infinite;
    }
    .floating-music {
      animation: music-bounce 6s ease-in-out infinite;
    }
    @keyframes float-around {
      0%, 100% { transform: translate(0, 0) rotate(0deg); }
      25% { transform: translate(10px, -15px) rotate(5deg); }
      50% { transform: translate(-5px, -25px) rotate(-3deg); }
      75% { transform: translate(15px, -10px) rotate(8deg); }
    }
    @keyframes sparkle-float {
      0%, 100% { transform: scale(1) rotate(0deg); opacity: 0.4; }
      50% { transform: scale(1.3) rotate(15deg); opacity: 0.7; }
    }
    @keyframes music-bounce {
      0%, 100% { transform: translateY(0) rotate(-5deg); }
      50% { transform: translateY(-20px) rotate(5deg); }
    }
    .heart-particle {
      position: fixed;
      font-size: 20px;
      pointer-events: none;
      z-index: 9999;
      animation: heart-float-up 1s ease-out forwards;
    }
    @keyframes heart-float-up {
      0% { transform: translateY(0) scale(1); opacity: 1; }
      100% { transform: translateY(-100px) scale(1.5); opacity: 0; }
    }
  `;
  document.head.appendChild(decoStyles);

  /* 💕 点击产生爱心 */
  function createHeart(x, y) {
    const hearts = ['💖', '💕', '💗', '💝', '💘'];
    const heart = document.createElement('div');
    heart.className = 'heart-particle';
    heart.textContent = hearts[Math.floor(Math.random() * hearts.length)];
    heart.style.left = x + 'px';
    heart.style.top = y + 'px';
    document.body.appendChild(heart);
    setTimeout(() => heart.remove(), 1000);
  }

  document.addEventListener('click', (e) => {
    if (!e.target.closest('button, a, input, [role="button"]')) {
      createHeart(e.clientX, e.clientY);
    }
  });

  /* 🎀 按钮点击涟漪效果（事件委托，支持动态添加的按钮） */
  document.body.addEventListener('click', (e) => {
    const btn = e.target.closest('button, .kawaii-button');
    if (!btn) return;

    const ripple = document.createElement('span');
    const isDark = document.documentElement.dataset.colorScheme === 'dark' ||
      (!document.documentElement.dataset.colorScheme &&
       window.matchMedia('(prefers-color-scheme: dark)').matches);
    ripple.style.cssText = `
      position: absolute;
      border-radius: 50%;
      background: ${isDark ? 'rgba(255, 0, 255, 0.3)' : 'rgba(255, 105, 180, 0.3)'};
      transform: scale(0);
      animation: ripple-effect 0.6s ease-out;
      pointer-events: none;
    `;

    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
    ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';

    btn.style.position = 'relative';
    btn.style.overflow = 'hidden';
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);

    createHeart(e.clientX, e.clientY);
  });

  /* 添加涟漪动画 keyframes */
  const rippleStyle = document.createElement('style');
  rippleStyle.textContent = `
    @keyframes ripple-effect {
      to { transform: scale(4); opacity: 0; }
    }
  `;
  document.head.appendChild(rippleStyle);
})();
