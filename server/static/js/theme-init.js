/**
 * Theme initialisation — runs synchronously before first paint to prevent FOUC.
 * Must be loaded as a blocking <script> (not type="module") in <head>.
 */
(function () {
  var root = document.documentElement;
  var storageKey = 'kawaii-color-scheme';
  var fallback = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  try {
    var saved = window.localStorage.getItem(storageKey);
    var scheme = saved === 'light' || saved === 'dark' ? saved : fallback;
    root.dataset.colorScheme = scheme;
  } catch (_error) {
    root.dataset.colorScheme = fallback;
  }

  // Populate <meta name="csrf-token"> from cookie for downstream JS modules.
  try {
    var match = document.cookie.match(/csrf_token=([^;]+)/);
    if (match) {
      var meta = document.querySelector('meta[name="csrf-token"]');
      if (meta) meta.content = decodeURIComponent(match[1]);
    }
  } catch (_e) {}
})();
