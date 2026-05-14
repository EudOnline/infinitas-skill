const SWIPE_THRESHOLD = 60;
const SWIPE_MAX = 120;

let activeCard = null;
let startX = 0;
let currentX = 0;

function onTouchStart(e) {
  if (e.target.closest('input, textarea, select, a, button')) return;
  const card = e.target.closest('article');
  if (!card) return;
  activeCard = card;
  startX = e.touches[0].clientX;
  card.style.transition = 'none';
}

function onTouchMove(e) {
  if (!activeCard) return;
  currentX = e.touches[0].clientX;
  const diff = currentX - startX;
  if (diff > 0) return;
  const clamped = Math.max(diff, -SWIPE_MAX);
  activeCard.style.transform = `translateX(${clamped}px)`;
  const actions = activeCard.querySelector('.swipe-actions');
  if (actions) {
    actions.style.opacity = Math.min(Math.abs(clamped) / SWIPE_THRESHOLD, 1);
  }
}

function onTouchEnd() {
  if (!activeCard) return;
  const diff = currentX - startX;
  activeCard.style.transition = 'transform 0.2s ease-out';
  if (diff < -SWIPE_THRESHOLD) {
    activeCard.style.transform = `translateX(-${SWIPE_MAX}px)`;
  } else {
    activeCard.style.transform = '';
    const actions = activeCard.querySelector('.swipe-actions');
    if (actions) actions.style.opacity = '0';
  }
  activeCard = null;
  startX = 0;
  currentX = 0;
}

export function initCardSwipe(containerSelector) {
  const containers = document.querySelectorAll(containerSelector);
  containers.forEach((container) => {
    container.addEventListener('touchstart', onTouchStart, { passive: true });
    container.addEventListener('touchmove', onTouchMove, { passive: false });
    container.addEventListener('touchend', onTouchEnd, { passive: true });
  });
}
