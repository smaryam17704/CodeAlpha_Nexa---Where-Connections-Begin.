(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }
  const csrftoken = getCookie('csrftoken');

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrftoken, 'X-Requested-With': 'XMLHttpRequest' },
      body: body || new URLSearchParams(),
    }).then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw data;
      return data;
    });
  }

  // ---- Like ----
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-like-btn');
    if (!btn) return;
    const pk = btn.dataset.postId;
    btn.disabled = true;
    post(`/social/post/${pk}/like/`).then((data) => {
      btn.classList.toggle('liked', data.liked);
      document.querySelectorAll(`.js-like-count-${pk}`).forEach((n) => { n.textContent = data.like_count; });
    }).catch(() => window.showToast('Something went wrong.', 'error'))
      .finally(() => { btn.disabled = false; });
  });

  // ---- Save ----
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-save-btn');
    if (!btn) return;
    const pk = btn.dataset.postId;
    btn.disabled = true;
    post(`/social/post/${pk}/save/`).then((data) => {
      btn.classList.toggle('saved', data.saved);
      window.showToast(data.saved ? 'Saved to your collection.' : 'Removed from saved.', 'success');
    }).catch(() => window.showToast('Something went wrong.', 'error'))
      .finally(() => { btn.disabled = false; });
  });

  // ---- Follow ----
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-follow-btn');
    if (!btn) return;
    const username = btn.dataset.username;
    btn.disabled = true;
    post(`/social/follow/${username}/`).then((data) => {
      document.querySelectorAll(`.js-follow-btn[data-username="${username}"]`).forEach((b) => {
        if (data.status === 'accepted') {
          b.textContent = 'Following';
        } else if (data.status === 'pending') {
          b.textContent = 'Requested';
        } else {
          b.textContent = 'Follow';
        }
        const isActive = data.status === 'accepted' || data.status === 'pending';
        b.classList.toggle('btn-secondary', isActive);
        b.classList.toggle('btn-primary', !isActive);
      });
      document.querySelectorAll(`.js-follower-count-${username}`).forEach((n) => { n.textContent = data.follower_count; });
      const message = data.status === 'accepted' ? 'Follow successful.'
        : data.status === 'pending' ? 'Follow request sent.'
        : 'Unfollow successful.';
      window.showToast(message, 'success');
    }).catch((err) => window.showToast(err.error || 'Something went wrong.', 'error'))
      .finally(() => { btn.disabled = false; });
  });

  // ---- Accept / reject follow requests ----
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-accept-follow-btn');
    if (!btn) return;
    const followId = btn.dataset.followId;
    btn.disabled = true;
    post(`/social/follow-requests/${followId}/accept/`).then(() => {
      const row = btn.closest('.notif-item');
      const actions = btn.parentElement;
      if (actions) actions.remove();
      window.showToast('Follow request accepted.', 'success');
    }).catch((err) => window.showToast(err.error || 'Something went wrong.', 'error'))
      .finally(() => { btn.disabled = false; });
  });

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-reject-follow-btn');
    if (!btn) return;
    const followId = btn.dataset.followId;
    btn.disabled = true;
    post(`/social/follow-requests/${followId}/reject/`).then(() => {
      const actions = btn.parentElement;
      if (actions) actions.remove();
      window.showToast('Follow request removed.', 'success');
    }).catch((err) => window.showToast(err.error || 'Something went wrong.', 'error'))
      .finally(() => { btn.disabled = false; });
  });

  // ---- Safe comment row builder (no innerHTML with user content — prevents XSS) ----
  function buildCommentRow(comment) {
    const row = document.createElement('div');
    row.className = 'comment-row';

    const avatarLink = document.createElement('a');
    avatarLink.href = `/accounts/u/${comment.author_username}/`;
    avatarLink.className = 'avatar';
    if (comment.avatar_url) {
      const img = document.createElement('img');
      img.src = comment.avatar_url;
      img.alt = '';
      avatarLink.appendChild(img);
    } else {
      avatarLink.textContent = (comment.author_display || '?').charAt(0).toUpperCase();
    }

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    const authorSpan = document.createElement('span');
    authorSpan.className = 'author';
    authorSpan.textContent = comment.author_display; // textContent — never interpreted as HTML
    bubble.appendChild(authorSpan);
    bubble.appendChild(document.createTextNode(comment.content)); // textContent-equivalent, safe

    if (comment.can_delete) {
      const deleteWrap = document.createElement('div');
      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'delete-btn js-delete-comment';
      deleteBtn.dataset.commentId = comment.id;
      deleteBtn.dataset.postId = comment.post_id || '';
      deleteBtn.textContent = 'Delete';
      deleteWrap.appendChild(deleteBtn);
      bubble.appendChild(deleteWrap);
    }

    row.appendChild(avatarLink);
    row.appendChild(bubble);
    return row;
  }

  function skeletonCommentRow() {
    const row = document.createElement('div');
    row.className = 'comment-row js-comment-skeleton';
    const avatar = document.createElement('div');
    avatar.className = 'avatar skeleton';
    avatar.style.cssText = 'width:28px;height:28px;';
    const bubble = document.createElement('div');
    bubble.className = 'skeleton';
    bubble.style.cssText = 'flex:1;height:34px;border-radius:12px;';
    row.appendChild(avatar);
    row.appendChild(bubble);
    return row;
  }

  // ---- Comment submit ----
  document.addEventListener('submit', (e) => {
    const form = e.target.closest('.js-comment-form');
    if (!form) return;
    e.preventDefault();
    const pk = form.dataset.postId;
    const input = form.querySelector('input[name="content"]');
    const submitBtn = form.querySelector('button[type="submit"]');
    const content = input.value.trim();
    if (!content) return;
    const body = new URLSearchParams({ content });
    submitBtn.disabled = true;
    input.disabled = true;
    post(`/social/post/${pk}/comment/`, body).then((data) => {
      input.value = '';
      const list = document.querySelector(`.js-comment-list-${pk}`);
      if (list) {
        list.appendChild(buildCommentRow({
          author_username: data.author, author_display: data.author_display,
          avatar_url: data.avatar_url, content: data.content, can_delete: true, post_id: pk,
        }));
      }
      document.querySelectorAll(`.js-comment-count-${pk}`).forEach((n) => { n.textContent = data.comment_count; });
    }).catch((err) => window.showToast(err.error || 'Your comment could not be posted.', 'error'))
      .finally(() => { submitBtn.disabled = false; input.disabled = false; input.focus(); });
  });

  // ---- Load more comments (server-paginated, not everything up front) ----
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-load-more-comments');
    if (!btn) return;
    const pk = btn.dataset.postId;
    const nextPage = btn.dataset.nextPage;
    const list = document.querySelector(`.js-comment-list-${pk}`);
    btn.disabled = true;
    const skeletons = [skeletonCommentRow(), skeletonCommentRow()];
    skeletons.forEach((s) => list.appendChild(s));

    fetch(`/social/post/${pk}/comments/?page=${nextPage}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then((res) => { if (!res.ok) throw new Error('load failed'); return res.json(); })
      .then((data) => {
        skeletons.forEach((s) => s.remove());
        data.comments.forEach((c) => list.appendChild(buildCommentRow(c)));
        if (data.has_next) {
          btn.dataset.nextPage = data.next_page;
          btn.disabled = false;
        } else {
          btn.remove();
        }
      })
      .catch(() => {
        skeletons.forEach((s) => s.remove());
        btn.disabled = false;
        window.showToast('Unable to load more comments.', 'error');
      });
  });

  // ---- Comment delete ----
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-delete-comment');
    if (!btn) return;
    const pk = btn.dataset.commentId;
    const postId = btn.dataset.postId;
    post(`/social/comment/${pk}/delete/`).then((data) => {
      btn.closest('.comment-row').remove();
      document.querySelectorAll(`.js-comment-count-${postId}`).forEach((n) => { n.textContent = data.comment_count; });
    }).catch(() => window.showToast('Unable to delete comment.', 'error'));
  });

  // ---- Post menu dropdown ----
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.js-menu-trigger');
    document.querySelectorAll('.post-menu-dropdown.open').forEach((d) => {
      if (!trigger || d !== trigger.nextElementSibling) d.classList.remove('open');
    });
    if (trigger) {
      trigger.nextElementSibling.classList.toggle('open');
      e.stopPropagation();
    }
  });

  // ---- Delete post confirm modal ----
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-delete-post');
    if (!btn) return;
    e.preventDefault();
    const deleteUrl = btn.dataset.deleteUrl;
    const redirectUrl = btn.dataset.redirect || '/';
    openConfirmModal({
      title: 'Delete this post?',
      body: 'This action cannot be undone. The post, its likes, comments, and saves will be permanently removed.',
      confirmLabel: 'Delete',
      onConfirm: () => {
        post(deleteUrl).then(() => {
          window.showToast('Post deleted.', 'success');
          setTimeout(() => { window.location.href = redirectUrl; }, 400);
        }).catch(() => window.showToast('Could not delete post.', 'error'));
      },
    });
  });

  window.openConfirmModal = function ({ title, body, confirmLabel, onConfirm }) {
    const previouslyFocused = document.activeElement;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <div class="modal-header">
          <h3 id="confirm-title" class="text-section-title">${title}</h3>
          <button class="btn-icon js-modal-close" aria-label="Close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="text-body" style="color:var(--text-secondary); margin-bottom: 20px;">${body}</p>
          <div class="flex gap-3 justify-between">
            <button class="btn btn-secondary btn-block js-modal-close">Cancel</button>
            <button class="btn btn-danger btn-block js-modal-confirm">${confirmLabel}</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    const focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    const getFocusable = () => Array.from(overlay.querySelectorAll(focusableSelector));

    const close = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKeydown);
      if (previouslyFocused && previouslyFocused.focus) previouslyFocused.focus();
    };

    function onKeydown(ev) {
      if (ev.key === 'Escape') {
        close();
        return;
      }
      if (ev.key === 'Tab') {
        const focusable = getFocusable();
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (ev.shiftKey && document.activeElement === first) {
          ev.preventDefault();
          last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
          ev.preventDefault();
          first.focus();
        }
      }
    }

    overlay.querySelectorAll('.js-modal-close').forEach((b) => b.addEventListener('click', close));
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    overlay.querySelector('.js-modal-confirm').addEventListener('click', () => { onConfirm(); close(); });
    document.addEventListener('keydown', onKeydown);
    overlay.querySelector('.js-modal-confirm').focus();
  };

  // ---- Multimedia post composer ----
  const composer = document.querySelector('.post-composer');
  if (composer) {
    const zone = composer.querySelector('.js-media-upload-zone');
    const preview = composer.querySelector('.js-media-preview');
    const placeholder = composer.querySelector('.js-media-placeholder');
    const prompt = composer.querySelector('.js-media-prompt');
    const hint = composer.querySelector('.js-media-hint');
    const meta = composer.querySelector('.js-media-file-meta');
    const clientError = composer.querySelector('.js-media-client-error');
    const removeButton = composer.querySelector('.js-media-remove');
    const browseButton = composer.querySelector('.js-media-browse');
    const inputs = Array.from(composer.querySelectorAll('.js-media-input-wrap input[type="file"]'));
    const options = Array.from(composer.querySelectorAll('[data-media-type-option]'));
    const accepted = {
      image: { label: 'image', extensions: ['jpg', 'jpeg', 'png', 'webp', 'gif'], hint: 'JPG, JPEG, PNG, WEBP, or GIF · up to 8MB' },
      video: { label: 'video', extensions: ['mp4', 'webm', 'mov'], hint: 'MP4, WEBM, or MOV · up to 100MB' },
      audio: { label: 'audio', extensions: ['mp3', 'wav', 'm4a'], hint: 'MP3, WAV, or M4A · up to 50MB' },
      document: { label: 'document', extensions: ['pdf', 'docx', 'xlsx', 'txt', 'csv'], hint: 'PDF, DOCX, XLSX, TXT, or CSV · up to 25MB' },
    };
    let currentType = composer.querySelector('input[name="media_type"]:checked')?.value || 'image';
    let objectUrl = null;

    const fileExtension = (file) => (file.name.split('.').pop() || '').toLowerCase();
    const formatBytes = (bytes) => {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };
    const showError = (message) => {
      if (clientError) clientError.textContent = message || '';
    };
    const clearPreview = () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = null;
      if (preview) preview.replaceChildren();
      if (meta) {
        meta.hidden = true;
        meta.textContent = '';
      }
      if (placeholder) placeholder.hidden = false;
      if (removeButton) removeButton.hidden = true;
    };
    const renderPreview = (file) => {
      clearPreview();
      if (!file) return;
      objectUrl = URL.createObjectURL(file);
      if (placeholder) placeholder.hidden = true;
      if (removeButton) removeButton.hidden = false;
      if (meta) {
        meta.hidden = false;
        meta.textContent = `${file.name} · ${formatBytes(file.size)}`;
      }
      if (!preview) return;
      if (currentType === 'image') {
        const image = document.createElement('img');
        image.src = objectUrl;
        image.alt = 'Selected image preview';
        preview.appendChild(image);
      } else if (currentType === 'video') {
        const video = document.createElement('video');
        video.src = objectUrl;
        video.controls = true;
        video.preload = 'metadata';
        preview.appendChild(video);
      } else if (currentType === 'audio') {
        const audio = document.createElement('audio');
        audio.src = objectUrl;
        audio.controls = true;
        preview.appendChild(audio);
      } else {
        const card = document.createElement('div');
        card.className = 'preview-document';
        const icon = document.createElement('span');
        icon.className = 'document-icon';
        icon.textContent = '▤';
        icon.setAttribute('aria-hidden', 'true');
        const name = document.createElement('strong');
        name.className = 'preview-document-name';
        name.textContent = file.name;
        card.append(icon, name);
        preview.appendChild(card);
      }
    };
    const activeInput = () => inputs.find((input) => input.dataset.mediaType === currentType);
    const clearFiles = () => {
      inputs.forEach((input) => { input.value = ''; });
      clearPreview();
      showError('');
    };
    const setType = (type, shouldClear = true) => {
      currentType = accepted[type] ? type : 'image';
      if (shouldClear) clearFiles();
      options.forEach((option) => option.classList.toggle('active', option.dataset.mediaTypeOption === currentType));
      composer.querySelectorAll('.js-media-input-wrap').forEach((wrap) => {
        wrap.classList.toggle('active', wrap.dataset.mediaInputWrap === currentType);
      });
      const rule = accepted[currentType];
      if (prompt) prompt.textContent = `Choose a ${rule.label} to share`;
      if (hint) hint.textContent = rule.hint;
      inputs.forEach((input) => { input.accept = rule.extensions.map((extension) => `.${extension}`).join(','); });
    };
    const acceptFile = (file) => {
      if (!file) return;
      const rule = accepted[currentType];
      if (!rule.extensions.includes(fileExtension(file))) {
        clearFiles();
        showError(`Unsupported file type. Please select a ${rule.label} file.`);
        return;
      }
      const input = activeInput();
      if (!input) return;
      try {
        const transfer = new DataTransfer();
        transfer.items.add(file);
        input.files = transfer.files;
      } catch (error) {
        // Browsers that do not allow assigning FileList still show the dropped preview.
      }
      showError('');
      renderPreview(file);
    };

    inputs.forEach((input) => {
      input.dataset.mediaType = input.closest('.js-media-input-wrap')?.dataset.mediaInputWrap || '';
      input.addEventListener('change', () => acceptFile(input.files[0]));
    });
    options.forEach((option) => {
      option.addEventListener('click', () => setType(option.dataset.mediaTypeOption));
    });
    browseButton?.addEventListener('click', () => activeInput()?.click());
    removeButton?.addEventListener('click', () => clearFiles());
    ['dragenter', 'dragover'].forEach((eventName) => zone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.add('is-dragging');
    }));
    ['dragleave', 'drop'].forEach((eventName) => zone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.remove('is-dragging');
    }));
    zone?.addEventListener('drop', (event) => acceptFile(event.dataTransfer?.files[0]));
    zone?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activeInput()?.click();
      }
    });
    setType(currentType, false);
  }

  // ---- Mark all notifications read ----
  const markReadBtn = document.querySelector('.js-mark-read');
  if (markReadBtn) {
    markReadBtn.addEventListener('click', () => {
      post('/notifications/mark-read/').then(() => {
        document.querySelectorAll('.notif-item.unread').forEach((n) => n.classList.remove('unread'));
        document.querySelectorAll('.js-unread-badge').forEach((n) => n.remove());
      });
    });
  }
})();
