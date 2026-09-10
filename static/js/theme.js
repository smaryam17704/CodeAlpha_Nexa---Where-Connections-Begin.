(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  function applyTheme(pref) {
    let resolved = pref;
    if (pref === 'system') {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', resolved);
  }

  const stored = document.documentElement.getAttribute('data-theme-pref') || getCookie('nexa_theme') || 'system';
  applyTheme(stored);

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const current = document.documentElement.getAttribute('data-theme-pref') || getCookie('nexa_theme') || 'system';
    if (current === 'system') applyTheme('system');
  });

  window.NexaTheme = {
    set(pref) {
      document.documentElement.setAttribute('data-theme-pref', pref);
      applyTheme(pref);
      document.cookie = `nexa_theme=${pref};path=/;max-age=31536000`;
      const csrftoken = getCookie('csrftoken');
      fetch('/settings/theme/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `theme=${pref}`,
      }).catch(() => {});
    },
  };
})();
