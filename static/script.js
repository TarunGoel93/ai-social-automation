/**
 * Social Media Automation Dashboard — script.js
 */

(() => {
  'use strict';

  /* ── Element refs ──────────────────────────────────────── */
  const toggle     = document.querySelector('.mode-toggle');
  const btnAI      = document.getElementById('btn-ai');
  const btnManual  = document.getElementById('btn-manual');
  const btnQueue   = document.getElementById('btn-queue');
  const formAI     = document.getElementById('form-ai');
  const formManual = document.getElementById('form-manual');
  const formQueue  = document.getElementById('form-queue');

  const allBtns   = [btnAI, btnManual, btnQueue];
  const allForms  = [formAI, formManual, formQueue];

  // AI fields
  const aiPrompt          = document.getElementById('ai-prompt');
  const aiPlatform        = document.getElementById('ai-platform');
  const aiTone            = document.getElementById('ai-tone');
  const aiScheduleToggle  = document.getElementById('ai-schedule-toggle');
  const aiSchedulePicker  = document.getElementById('ai-schedule-picker');
  const aiScheduledTime   = document.getElementById('ai-scheduled-time');
  const submitAI          = document.getElementById('submit-ai');

  // Manual fields
  const manualImage          = document.getElementById('manual-image');
  const manualCaption        = document.getElementById('manual-caption');
  const manualPlatform       = document.getElementById('manual-platform');
  const manualScheduleToggle = document.getElementById('manual-schedule-toggle');
  const manualSchedulePicker = document.getElementById('manual-schedule-picker');
  const manualScheduledTime  = document.getElementById('manual-scheduled-time');
  const submitManual         = document.getElementById('submit-manual');
  const uploadZone           = document.getElementById('upload-zone');
  const uploadPlaceholder    = document.getElementById('upload-placeholder');
  const uploadPreview        = document.getElementById('upload-preview');
  const previewImg           = document.getElementById('preview-img');
  const removeImage          = document.getElementById('remove-image');

  // Status
  const statusBanner  = document.getElementById('status-banner');
  const statusIcon    = document.getElementById('status-icon');
  const statusMessage = document.getElementById('status-message');
  const statusClose   = document.getElementById('status-close');

  /* ── Min datetime = now+1min ───────────────────────────── */
  function setMinDatetime(input) {
    const now = new Date();
    now.setSeconds(0, 0);
    now.setMinutes(now.getMinutes() + 1);
    const p = n => String(n).padStart(2, '0');
    input.min = `${now.getFullYear()}-${p(now.getMonth()+1)}-${p(now.getDate())}T${p(now.getHours())}:${p(now.getMinutes())}`;
  }

  /* ── Mode Toggle (3 tabs) ──────────────────────────────── */
  function activateMode(mode) {
    const idx = { ai: 0, manual: 1, queue: 2 }[mode] ?? 0;

    allBtns.forEach((btn, i) => {
      const active = i === idx;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-selected', String(active));
    });

    // Slide the indicator
    toggle.dataset.tab = idx;

    allForms.forEach((form, i) => {
      if (i === idx) form.removeAttribute('hidden');
      else           form.setAttribute('hidden', '');
    });

    hideStatus();

    if (mode === 'queue') loadQueue();
  }

  btnAI.addEventListener('click',     () => activateMode('ai'));
  btnManual.addEventListener('click', () => activateMode('manual'));
  btnQueue.addEventListener('click',  () => activateMode('queue'));

  /* ── Schedule Toggle wiring ────────────────────────────── */
  function wireSchedule(checkbox, picker, dtInput, btn, labelNow, labelLater) {
    checkbox.addEventListener('change', () => {
      const on = checkbox.checked;
      if (on) { picker.removeAttribute('hidden'); setMinDatetime(dtInput); }
      else      picker.setAttribute('hidden', '');
      btn.querySelector('.btn-text').textContent = on ? labelLater : labelNow;
    });
  }
  wireSchedule(aiScheduleToggle,     aiSchedulePicker,     aiScheduledTime,     submitAI,     'Generate & Post', 'Schedule Post');
  wireSchedule(manualScheduleToggle, manualSchedulePicker, manualScheduledTime, submitManual, 'Post Now',        'Schedule Post');

  /* ── Image Preview ─────────────────────────────────────── */
  function showPreview(file) {
    if (!file || !file.type.startsWith('image/')) return;
    previewImg.src = URL.createObjectURL(file);
    uploadPlaceholder.setAttribute('hidden', '');
    uploadPreview.removeAttribute('hidden');
  }
  function clearPreview() {
    previewImg.src = '';
    manualImage.value = '';
    uploadPreview.setAttribute('hidden', '');
    uploadPlaceholder.removeAttribute('hidden');
  }
  manualImage.addEventListener('change', e => { if (e.target.files[0]) showPreview(e.target.files[0]); });
  removeImage.addEventListener('click',  e => { e.preventDefault(); e.stopPropagation(); clearPreview(); });
  uploadZone.addEventListener('dragover',  e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
  uploadZone.addEventListener('dragleave', ()  => uploadZone.classList.remove('dragover'));
  uploadZone.addEventListener('drop', e => {
    e.preventDefault(); uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) { const dt = new DataTransfer(); dt.items.add(file); manualImage.files = dt.files; showPreview(file); }
  });

  /* ── Status Banner ─────────────────────────────────────── */
  function showStatus(type, msg) {
    statusBanner.className = 'status-banner ' + type;
    statusIcon.textContent    = type === 'success' ? '✓' : '✕';
    statusMessage.textContent = msg;
    statusBanner.removeAttribute('hidden');
    if (type === 'success') setTimeout(hideStatus, 7000);
  }
  function hideStatus() { statusBanner.setAttribute('hidden', ''); }
  statusClose.addEventListener('click', hideStatus);

  /* ── Loading ───────────────────────────────────────────── */
  function setLoading(btn, on) { btn.disabled = on; btn.classList.toggle('loading', on); }

  /* ── Field flags ───────────────────────────────────────── */
  function flag(el, bad) { el.style.borderColor = bad ? 'var(--error-fg)' : ''; }
  [aiPrompt, aiPlatform, aiTone, manualCaption, manualPlatform, aiScheduledTime, manualScheduledTime].forEach(el => {
    el.addEventListener('input',  () => flag(el, false));
    el.addEventListener('change', () => flag(el, false));
  });
  manualImage.addEventListener('change', () => { uploadZone.style.borderColor = ''; });

  /* ── AI Submit ─────────────────────────────────────────── */
  submitAI.addEventListener('click', async () => {
    const prompt    = aiPrompt.value.trim();
    const platform  = aiPlatform.value;
    const tone      = aiTone.value.trim();
    const useSchedule = aiScheduleToggle.checked;
    const scheduled = useSchedule ? aiScheduledTime.value : '';

    let ok = true;
    if (!prompt)                   { flag(aiPrompt,        true); ok = false; }
    if (!platform)                 { flag(aiPlatform,      true); ok = false; }
    if (useSchedule && !scheduled) { flag(aiScheduledTime, true); ok = false; }
    if (!ok) { showStatus('error', 'Please fill in all required fields.'); return; }

    setLoading(submitAI, true); hideStatus();
    try {
      const res  = await fetch('/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'ai', prompt, tone, platforms: platform, scheduled_time: scheduled }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        showStatus('success', data.message || 'Done!');
        aiPrompt.value = ''; aiPlatform.value = ''; aiTone.value = '';
        aiScheduleToggle.checked = false; aiSchedulePicker.setAttribute('hidden','');
        submitAI.querySelector('.btn-text').textContent = 'Generate & Post';
      } else { showStatus('error', data.message || 'Something went wrong.'); }
    } catch { showStatus('error', 'Network error — could not reach the server.'); }
    finally  { setLoading(submitAI, false); }
  });

  /* ── Manual Submit ─────────────────────────────────────── */
  submitManual.addEventListener('click', async () => {
    const caption   = manualCaption.value.trim();
    const platform  = manualPlatform.value;
    const imageFile = manualImage.files[0];
    const useSchedule = manualScheduleToggle.checked;
    const scheduled = useSchedule ? manualScheduledTime.value : '';

    let ok = true;
    if (!caption)                  { flag(manualCaption,      true); ok = false; }
    if (!platform)                 { flag(manualPlatform,     true); ok = false; }
    if (!imageFile)                { uploadZone.style.borderColor = 'var(--error-fg)'; ok = false; }
    if (useSchedule && !scheduled) { flag(manualScheduledTime,true); ok = false; }
    if (!ok) { showStatus('error', 'Please fill in all required fields and upload an image.'); return; }
    if (!imageFile.type.startsWith('image/')) { showStatus('error', 'Only image files are allowed.'); return; }

    setLoading(submitManual, true); hideStatus();
    const fd = new FormData();
    fd.append('mode', 'manual'); fd.append('caption', caption);
    fd.append('platforms', platform); fd.append('image', imageFile);
    fd.append('scheduled_time', scheduled);
    try {
      const res  = await fetch('/submit', { method: 'POST', body: fd });
      const data = await res.json();
      if (data.status === 'success') {
        showStatus('success', data.message || 'Done!');
        manualCaption.value = ''; manualPlatform.value = ''; clearPreview();
        manualScheduleToggle.checked = false; manualSchedulePicker.setAttribute('hidden','');
        submitManual.querySelector('.btn-text').textContent = 'Post Now';
      } else { showStatus('error', data.message || 'Something went wrong.'); }
    } catch { showStatus('error', 'Network error — could not reach the server.'); }
    finally  { setLoading(submitManual, false); }
  });

  /* ── Queue Tab ─────────────────────────────────────────── */
  const queueList    = document.getElementById('queue-list');
  const queueRefresh = document.getElementById('queue-refresh');
  let   activeFilter = 'all';

  async function loadQueue() {
    queueList.innerHTML = '<p class="queue-empty">Loading…</p>';
    try {
      const url = activeFilter === 'all' ? '/posts' : `/posts?status=${activeFilter}`;
      const res  = await fetch(url);
      const data = await res.json();
      const posts = data.posts || [];
      if (!posts.length) {
        queueList.innerHTML = '<p class="queue-empty">No posts yet. Schedule one from AI or Manual tab.</p>';
        return;
      }
      queueList.innerHTML = '';
      posts.forEach(p => {
        const card = document.createElement('div');
        card.className = `queue-card status-${p.status}`;
        const title = p.mode === 'ai'
          ? `✦ AI · ${(p.prompt || '').slice(0, 55)}${p.prompt && p.prompt.length > 55 ? '…' : ''}`
          : `✎ Manual · ${(p.caption || '').slice(0, 55)}${p.caption && p.caption.length > 55 ? '…' : ''}`;
        const time = p.scheduled_time
          ? new Date(p.scheduled_time).toLocaleString(undefined, {dateStyle:'medium',timeStyle:'short'})
          : '—';
        const badgeClass = `badge-${p.status}`;
        const actions = p.status === 'pending'
          ? `<div class="qc-btn-row">
               <button class="qc-btn" onclick="firePost(${p.id})">▶ Send now</button>
               <button class="qc-btn danger" onclick="deletePost(${p.id})">✕ Delete</button>
             </div>`
          : '';
        const errLine = p.error_msg
          ? `<div class="qc-meta qc-error">Error: ${p.error_msg}</div>` : '';
        const firedLine = p.fired_at
          ? `<div class="qc-meta">Sent: ${new Date(p.fired_at + 'Z').toLocaleString(undefined, {dateStyle:'medium',timeStyle:'short'})}</div>` : '';
        card.innerHTML = `
          <div class="qc-body">
            <div class="qc-title">${title}</div>
            <div class="qc-meta">📅 ${time} &nbsp;·&nbsp; 🌐 ${p.platforms} &nbsp;·&nbsp; ${p.mode.toUpperCase()}</div>
            ${firedLine}${errLine}
          </div>
          <div class="qc-actions">
            <span class="qc-badge ${badgeClass}">${p.status}</span>
            ${actions}
          </div>`;
        queueList.appendChild(card);
      });
    } catch(e) {
      queueList.innerHTML = '<p class="queue-empty">Failed to load posts.</p>';
    }
  }

  window.firePost = async (id) => {
    if (!confirm('Send this post to n8n right now?')) return;
    const res  = await fetch(`/posts/${id}/fire`, {method:'POST'});
    const data = await res.json();
    showStatus(data.status, data.message);
    loadQueue();
  };
  window.deletePost = async (id) => {
    if (!confirm('Delete this queued post?')) return;
    const res  = await fetch(`/posts/${id}`, {method:'DELETE'});
    const data = await res.json();
    showStatus(data.status, data.message);
    loadQueue();
  };

  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.filter;
      loadQueue();
    });
  });

  queueRefresh && queueRefresh.addEventListener('click', loadQueue);

  // Auto-refresh every 30s when queue tab is active
  setInterval(() => {
    if (!formQueue.hasAttribute('hidden')) loadQueue();
  }, 30000);

  /* ── Webhook health check ──────────────────────────────── */
  const wsDot   = document.getElementById('ws-dot');
  const wsLabel = document.getElementById('ws-label');
  async function checkWebhook() {
    if (!wsDot) return;
    wsDot.className = 'ws-dot checking'; wsLabel.textContent = 'checking n8n…';
    try {
      const res  = await fetch('/health');
      const data = await res.json();
      if (data.status === 'ok') {
        wsDot.className = 'ws-dot ok'; wsLabel.textContent = 'n8n connected';
      } else {
        wsDot.className = 'ws-dot error';
        wsLabel.textContent = data.http_status === 404
          ? 'n8n: workflow not active'
          : `n8n: ${data.message}`;
      }
    } catch {
      wsDot.className = 'ws-dot error'; wsLabel.textContent = 'n8n unreachable';
    }
  }
  checkWebhook();
  setInterval(checkWebhook, 60000);

})();
