// Keep the copyright and analytics preferences identical across every page.
document.querySelectorAll('[data-year]').forEach((year) => {
  year.textContent = new Date().getFullYear();
});

(() => {
  const key = 'stuart-cs-analytics-opt-out';
  const choice = new URLSearchParams(window.location.search).get('analytics');
  try {
    if (choice === 'off') localStorage.setItem(key, '1');
    if (choice === 'on') localStorage.removeItem(key);
  } catch (error) { /* Storage may be unavailable in private browsing. */ }
  if (choice === 'off') return;
  try {
    if (localStorage.getItem(key) === '1') return;
  } catch (error) { /* Continue without a stored preference. */ }
  const beacon = document.createElement('script');
  beacon.type = 'module';
  beacon.src = 'https://static.cloudflareinsights.com/beacon.min.js';
  beacon.setAttribute('data-cf-beacon', JSON.stringify({token: 'd771156b307c47318e2d12b2369e3d47'}));
  document.body.appendChild(beacon);
})();
