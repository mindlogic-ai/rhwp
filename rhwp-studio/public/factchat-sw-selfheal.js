// factchat HWP agent: self-heal from a stale service worker installed by a
// prior PWA build. Without this, the SW intercepts asset fetches and serves
// cached responses pointing at filenames that no longer exist after an engine
// upgrade. Safe no-op when no SW is registered.
//
// 확장 빌드의 CSP가 인라인 스크립트를 금지하므로(#1444) theme-init.js와 같이
// 외부 파일로 둔다. defer/module 없이 동기 로드되어 번들보다 먼저 실행된다.
(function () {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker
    .getRegistrations()
    .then(function (regs) {
      var hadSw = false;
      regs.forEach(function (r) {
        if (r.scope && (r.scope.indexOf('/rhwp/') !== -1 || r.scope.indexOf('/static/rhwp/') !== -1 || r.scope.indexOf('/studio/') !== -1)) {
          hadSw = true;
          r.unregister();
        }
      });
      if (hadSw && 'caches' in window) {
        caches.keys().then(function (keys) {
          keys.forEach(function (k) {
            caches.delete(k);
          });
          location.reload();
        });
      }
    })
    .catch(function () {});
})();
