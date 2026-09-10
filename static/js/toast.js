(function () {
  function region() {
    let el = document.getElementById('toast-region');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toast-region';
      document.body.appendChild(el);
    }
    return el;
  }

  window.showToast = function (message, type = 'success') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    region().appendChild(el);
    setTimeout(() => {
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 200);
    }, 3200);
  };

  // Surface Django messages (rendered as data attributes) as toasts on load.
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-django-message]').forEach((node) => {
      window.showToast(node.dataset.djangoMessage, node.dataset.messageType || 'success');
    });
  });
})();
