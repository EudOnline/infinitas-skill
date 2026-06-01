const { PurgeCSS } = require('purgecss');
const fs = require('fs');

async function run() {
  const result = await new PurgeCSS().purge({
    content: [
      'server/templates/**/*.html',
      'server/static/js/**/*.js',
    ],
    css: ['server/static/css/input.css'],
    safelist: {
      standard: [
        'hidden',
        'cursor-pointer',
        'focus-mode',
        'page-console',
        'is-active',
        'is-open',
        'user-panel--flip',
        'user-trigger',
        'toast--info',
        'toast--success',
        'toast--error',
        'toast--warning',
        'kawaii-button--primary',
        'kawaii-button--secondary',
        'kawaii-button--ghost',
        'kawaii-button--loading',
        'kawaii-badge--success',
        'kawaii-badge--pending',
        'kawaii-badge--error',
        'kawaii-badge--running',
        'kawaii-tag--blue',
        'kawaii-tag--green',
        'kawaii-tag--pink',
        'bg-option',
        'bg-option--gradient',
        'search-result__readiness--fresh',
        'search-result__readiness--stale',
        'review-detail-badge--approve',
        'review-detail-badge--comment',
        'review-detail-badge--reject',
        'toast-out',
        /^data-/,
        /^aria-/,
      ],
      deep: [
        /search-result/,
        /search-install/,
        /review-detail/,
        /session-panel/,
        /user-panel/,
        /console-auth-modal/,
        /auth-modal/,
        /toast/,
        /kawaii-/,
        /bg-option/,
      ],
      greedy: [
        /prefers-color-scheme/,
        /keyframes/,
      ],
      keyframes: ['toast-out'],
    },
  });

  const purgedPath = 'server/static/css/.input.purged.css';
  fs.writeFileSync(purgedPath, result[0].css);
  const saved = result[0].rejected?.length || 0;
  console.log(`PurgeCSS complete. Removed ${saved} unused selectors. Written to ${purgedPath}`);
}

run().catch(err => {
  console.error('PurgeCSS failed:', err);
  process.exit(1);
});
