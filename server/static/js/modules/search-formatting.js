import { currentPageLanguage } from './config.js';

function localizedValue(value, entries) {
  const entry = entries[String(value || '').toLowerCase()];
  if (!entry) return value || '';
  return entry[currentPageLanguage()] || entry.zh;
}

export function formatAudienceType(audienceType) {
  return localizedValue(audienceType, {
    private: { zh: '私人', en: 'Private' },
    authenticated: { zh: '已认证', en: 'Authenticated' },
    grant: { zh: '令牌共享', en: 'Shared by token' },
    public: { zh: '公开', en: 'Public' },
  });
}

export function formatInstallScope(scope) {
  return localizedValue(scope, {
    public: { zh: '公开', en: 'Public' },
    me: { zh: '仅自己', en: 'Only me' },
    grant: { zh: '授权', en: 'Grant' },
  });
}

export function formatListingMode(mode) {
  return localizedValue(mode, {
    listed: { zh: '已列出', en: 'Listed' },
    direct_only: { zh: '仅直链', en: 'Direct only' },
  });
}
