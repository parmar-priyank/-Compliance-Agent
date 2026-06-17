const QC_ITEMS = window.__QC_ITEMS__;
let sessionId = null;
let results   = {};

// ── Auth helpers ──────────────────────────────────────────────────────────
function authToken() {
  return sessionStorage.getItem('qc_token') || '';
}
function authHeaders() {
  const t = authToken();
  return t ? { 'X-Auth-Token': t } : {};
}
function authFetch(url, opts = {}) {
  opts.headers = Object.assign({}, opts.headers || {}, authHeaders());
  return fetch(url, opts);
}

// ── Sign out ──────────────────────────────────────────────────────────────
function signOut() {
  const modal    = document.getElementById('signout-modal');
  const bodyText = document.getElementById('signout-modal-body');
  const btn      = document.getElementById('signout-confirm-btn');
  if (sessionId) {
    bodyText.textContent = 'Your current progress is saved and can be resumed later.';
    btn.textContent      = 'Sign out';
  } else {
    bodyText.textContent = 'Are you sure you want to sign out?';
    btn.textContent      = 'Sign out';
  }
  modal.classList.add('show');
}
function closeSignOutModal() {
  document.getElementById('signout-modal').classList.remove('show');
}
async function confirmSignOut() {
  const btn = document.getElementById('signout-confirm-btn');
  btn.disabled    = true;
  btn.textContent = 'Signing out…';
  await authFetch('/api/logout', { method: 'POST' }).catch(() => {});
  sessionStorage.removeItem('qc_token');
  sessionStorage.removeItem('qc_role');
  sessionStorage.removeItem('qc_name');
  window.location.href = '/login';
}

// ── Boot ──────────────────────────────────────────────────────────────────
// Clear any stale localStorage from previous versions — DB is source of truth
localStorage.removeItem('qc_session');

(async function bootAuth() {
  const token = authToken();
  if (!token) { window.location.href = '/login'; return; }

  let user;
  try {
    const r = await fetch('/api/me', { headers: { 'X-Auth-Token': token } });
    if (!r.ok) { window.location.href = '/login'; return; }
    user = await r.json();
  } catch {
    window.location.href = '/login';
    return;
  }

  const name = user.name || sessionStorage.getItem('qc_name') || '?';
  document.getElementById('topbar-username').textContent = name;
  document.getElementById('topbar-avatar').textContent   = name[0].toUpperCase();

  // Always load from the database — never from localStorage
  try {
    const r    = await authFetch('/api/my-last-project');
    const data = await r.json();
    if (data.ok && data.session_id) showResumeBanner(data);
  } catch { /* no saved project */ }
})();

// ── Resume banner ─────────────────────────────────────────────────────────
let _resumeData = null;

function showResumeBanner(data) {
  _resumeData = data;
  const done = (data.yes || 0) + (data.no || 0) + (data.na || 0);
  document.getElementById('resume-customer').textContent =
    data.customer || 'Unknown customer';
  document.getElementById('resume-meta').textContent =
    `${data.date || '—'}  ·  ${done} of ${QC_ITEMS.length} checks completed  ·  ✓ ${data.yes}  ✗ ${data.no}  – ${data.na}`;
  document.getElementById('resume-banner').style.display = 'flex';
}

function resumeProject() {
  if (!_resumeData) return;
  sessionId = _resumeData.session_id;

  setInfoField('field-quote-number', 'info-quote-number', null); // clear extras
  document.getElementById('info-customer').textContent  = _resumeData.customer  || '—';
  document.getElementById('info-address').textContent   = _resumeData.address   || '—';
  document.getElementById('info-date').textContent      = _resumeData.date      || '—';
  document.getElementById('info-agreement').textContent = _resumeData.agreement || '—';

  results = {};
  (_resumeData.results || []).forEach(r => {
    results[r.key] = r;
    updateTable(r);
  });

  updateStats();
  showAppScreen();
}

function dismissResume() {
  _resumeData = null;
  document.getElementById('resume-banner').style.display = 'none';
}

// ── Persistence — DB only, no localStorage ───────────────────────────────
function saveState() {
  syncProject(); // persist to DB immediately
}
function clearState() {
  // nothing to clear locally — DB is the source of truth
}

// ── Landing ───────────────────────────────────────────────────────────────
// Excel file is optional — remembered if selected before or after the PDF.
let _pendingExcel = null;

function _setupDropZone(zoneId, inputId, onFile) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;
  zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('active'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('active'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('active');
    if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', e => {
    if (e.target.files[0]) onFile(e.target.files[0]);
    input.value = '';
  });
}

function _markZoneReady(zoneId, badgeId, nameId, hintId, file) {
  const zone  = document.getElementById(zoneId);
  const badge = document.getElementById(badgeId);
  const name  = document.getElementById(nameId);
  const hint  = document.getElementById(hintId);
  if (!zone) return;
  zone.classList.add('ready');
  if (hint)  hint.style.display  = 'none';
  if (badge) badge.style.display = 'flex';
  if (name)  name.textContent    = file.name;
}

// Excel zone — just stores the file, doesn't trigger anything
_setupDropZone('zone-excel', 'landing-input-excel', file => {
  _pendingExcel = file;
  _markZoneReady('zone-excel', 'zone-excel-badge', 'zone-excel-name', 'zone-excel-hint', file);
});

// PDF zone — triggers the full upload flow immediately (original behaviour)
_setupDropZone('zone-pdf', 'landing-input', file => {
  _markZoneReady('zone-pdf', 'zone-pdf-badge', 'zone-pdf-name', 'zone-pdf-hint', file);
  uploadAgreement(file);
});

async function uploadAgreement(file) {
  if (!file) return;
  const loading = document.getElementById('landing-loading');
  const msg     = document.getElementById('landing-loading-msg');
  loading.classList.add('show');

  try {
    // Step 1: upload PDF agreement
    if (msg) msg.textContent = 'Reading agreement and extracting customer details…';
    const fd = new FormData();
    fd.append('file', file);
    const r = await authFetch('/api/upload-agreement', { method: 'POST', body: fd });
    if (r.status === 401) { window.location.href = '/login'; return; }
    const data = await r.json();
    sessionId = data.session_id;

    // Step 2: if an Excel was also selected, import it into the same session
    if (_pendingExcel) {
      if (msg) msg.textContent = 'Importing QC checklist from Excel…';
      const fdXl = new FormData();
      fdXl.append('file',       _pendingExcel);
      fdXl.append('session_id', sessionId);
      const rXl = await authFetch('/api/upload-excel', { method: 'POST', body: fdXl });
      if (rXl.ok) {
        const xlData = await rXl.json();
        (xlData.results || []).forEach(r => {
          results[r.key] = r;
          updateTable(r);
        });
      }
    }

    // Populate sidebar
    document.getElementById('info-customer').textContent  = data.customer_name || '—';
    document.getElementById('info-address').textContent   = data.address        || '—';
    document.getElementById('info-date').textContent      = new Date().toLocaleDateString('en-AU');
    document.getElementById('info-agreement').textContent = file.name;

    // Reset extra fields panel
    ['field-quote-number','field-phone','field-email','field-system-price',
     'field-deposit','field-install-date','field-roof-type','field-stories',
     'field-phase','field-signed-by'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    const toggle = document.getElementById('details-toggle');
    const panel  = document.getElementById('project-extra-fields');
    if (toggle) { toggle.style.display = 'none'; toggle.textContent = 'Show more details ›'; }
    if (panel)  panel.style.display = 'none';

    setInfoField('field-quote-number', 'info-quote-number', data.quote_number);
    setInfoField('field-phone',        'info-phone',        data.customer_phone);
    setInfoField('field-email',        'info-email',        data.customer_email);
    setInfoField('field-system-price', 'info-system-price', data.system_price   ? `$${Number(data.system_price).toLocaleString()}`  : null);
    setInfoField('field-deposit',      'info-deposit',      data.deposit        ? `$${Number(data.deposit).toLocaleString()}`        : null);
    setInfoField('field-install-date', 'info-install-date', data.proposed_install_date);
    setInfoField('field-roof-type',    'info-roof-type',    data.roof_type);
    setInfoField('field-stories',      'info-stories',      data.stories);
    setInfoField('field-phase',        'info-phase',        data.inverter_phase);
    setInfoField('field-signed-by',    'info-signed-by',    data.signed_by);

    updateStats();
    showAppScreen();
    syncProject();
  } catch (e) {
    alert('Upload failed: ' + e.message);
  } finally {
    loading.classList.remove('show');
    if (msg) msg.textContent = 'Reading agreement and extracting customer details…';
  }
}

function setInfoField(fieldId, elId, value) {
  const field = document.getElementById(fieldId);
  const el    = document.getElementById(elId);
  if (!field || !el) return;
  if (value) {
    el.textContent      = value;
    field.style.display = '';
    // Show the toggle button whenever at least one extra field has a value
    const toggle = document.getElementById('details-toggle');
    if (toggle) toggle.style.display = '';
  } else {
    field.style.display = 'none';
  }
}

function toggleProjectDetails() {
  const panel  = document.getElementById('project-extra-fields');
  const toggle = document.getElementById('details-toggle');
  const open   = panel.style.display !== 'none';
  panel.style.display  = open ? 'none' : 'block';
  toggle.textContent   = open ? 'Show more details ›' : 'Hide details ›';
}

// ── App screen helpers ────────────────────────────────────────────────────
function showAppScreen() {
  document.getElementById('landing-screen').style.display  = 'none';
  document.getElementById('app-screen').style.display      = 'block';
  document.getElementById('project-actions').style.display = 'flex';
  refreshTableVisibility();
}

function refreshTableVisibility() {
  const hasResults = Object.keys(results).length > 0;
  document.getElementById('results-empty').style.display      = hasResults ? 'none'  : 'block';
  document.getElementById('results-table-wrap').style.display = hasResults ? 'block' : 'none';
}

// ── Results table ─────────────────────────────────────────────────────────
function updateTable(data) {
  const row = document.getElementById('row-' + data.key);
  if (!row) return;
  const cls = (data.result || 'pending').toLowerCase().replace('/', '');
  const tds = row.querySelectorAll('td');
  tds[2].innerHTML   = `<span class="td-result ${cls}">${data.result || '—'}</span>`;
  tds[3].textContent = data.filename || '—';
  tds[4].textContent = data.remark   || '—';
}

function updateStats() {
  const vals = Object.values(results);
  const yes  = vals.filter(r => r.result === 'Yes').length;
  const no   = vals.filter(r => r.result === 'No').length;
  const na   = vals.filter(r => r.result === 'N/A').length;
  document.getElementById('stat-yes').textContent = `✓ ${yes} Yes`;
  document.getElementById('stat-no').textContent  = `✗ ${no} No`;
  document.getElementById('stat-na').textContent  = `– ${na} N/A`;
}

// ── Batch ZIP Upload ──────────────────────────────────────────────────────
(function setupBatchZip() {
  const input = document.getElementById('batch-zip-input');
  if (!input) return;
  input.addEventListener('change', e => {
    if (e.target.files[0]) startBatchUpload(e.target.files[0]);
    input.value = '';
  });
})();

function openBatchModal() {
  document.getElementById('batch-modal-status').textContent   = 'Uploading and running all checks…';
  document.getElementById('batch-progress-fill').style.width  = '0%';
  document.getElementById('batch-progress-label').textContent = '0 / 0';
  const log = document.getElementById('batch-log');
  log.innerHTML     = '';
  log.style.display = 'none';
  document.getElementById('batch-modal-actions').style.display = 'none';
  document.getElementById('batch-modal').classList.add('show');
}

function closeBatchModal() {
  document.getElementById('batch-modal').classList.remove('show');
}

function batchLog(msg, type) {
  const log  = document.getElementById('batch-log');
  log.style.display = 'block';
  const line = document.createElement('div');
  line.className   = 'batch-log-line' + (type ? ' ' + type : '');
  line.textContent = msg;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

async function startBatchUpload(file) {
  if (!sessionId) { alert('Please upload the signed agreement first.'); return; }
  openBatchModal();

  const fd = new FormData();
  fd.append('session_id', sessionId);
  fd.append('zip_file',   file);

  let data;
  try {
    const r = await authFetch('/api/batch-check', { method: 'POST', body: fd });
    if (r.status === 401) { window.location.href = '/login'; return; }
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${r.status}`);
    }
    data = await r.json();
  } catch (e) {
    document.getElementById('batch-modal-status').textContent = 'Failed: ' + e.message;
    document.getElementById('batch-modal-actions').style.display = 'flex';
    return;
  }

  const allResults = data.results || [];
  const skipped    = data.skipped  || [];
  const total      = allResults.length;

  allResults.forEach((item, idx) => {
    results[item.key] = item;
    updateTable(item);

    const pct = Math.round(((idx + 1) / total) * 100);
    document.getElementById('batch-progress-fill').style.width  = pct + '%';
    document.getElementById('batch-progress-label').textContent = `${idx + 1} / ${total}`;

    const icon = item.result === 'Yes' ? '✓' : item.result === 'No' ? '✗' : '–';
    const type = item.result === 'Yes' ? 'log-yes' : item.result === 'No' ? 'log-no' : 'log-na';
    batchLog(`${icon}  ${item.label}: ${item.result}`, type);
  });

  skipped.forEach(s => batchLog(`⚠  Skipped — ${s.filename}: ${s.reason}`, 'log-skip'));

  updateStats();
  refreshTableVisibility();
  syncProject();

  const yes = allResults.filter(r => r.result === 'Yes').length;
  const no  = allResults.filter(r => r.result === 'No').length;
  const na  = allResults.filter(r => r.result === 'N/A').length;
  document.getElementById('batch-modal-status').textContent =
    `Done — ${total} checks completed` +
    (skipped.length ? `, ${skipped.length} skipped` : '');
  document.getElementById('batch-modal-actions').style.display = 'flex';
}

document.getElementById('batch-modal').addEventListener('click', function(e) {
  if (e.target === this) closeBatchModal();
});

// ── Sync project to server ────────────────────────────────────────────────
function syncProject() {
  if (!sessionId) return;
  authFetch('/api/sync-project', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      session_id: sessionId,
      customer:   document.getElementById('info-customer').textContent,
      address:    document.getElementById('info-address').textContent,
      agreement:  document.getElementById('info-agreement').textContent,
    }),
  }).catch(() => {});
}

// ── New Project ───────────────────────────────────────────────────────────
function newProject() {
  document.getElementById('new-project-modal').classList.add('show');
}
function closeNewProjectModal() {
  document.getElementById('new-project-modal').classList.remove('show');
}
async function confirmNewProject(choice) {
  closeNewProjectModal();
  if (choice === 'discard' && sessionId) {
    await authFetch(`/api/session/${sessionId}`, { method: 'DELETE' }).catch(() => {});
  }
  clearState();
  clearUI();
}

document.getElementById('new-project-modal').addEventListener('click', function(e) {
  if (e.target === this) closeNewProjectModal();
});
document.getElementById('signout-modal').addEventListener('click', function(e) {
  if (e.target === this) closeSignOutModal();
});

function clearUI() {
  results       = {};
  sessionId     = null;
  _pendingExcel = null;

  // Reset table rows
  document.querySelectorAll('#results-tbody tr').forEach(row => {
    const tds = row.querySelectorAll('td');
    tds[2].innerHTML   = '<span class="td-result pending">—</span>';
    tds[3].textContent = '—';
    tds[4].textContent = '—';
  });

  updateStats();

  document.getElementById('app-screen').style.display      = 'none';
  document.getElementById('landing-screen').style.display  = 'flex';
  document.getElementById('project-actions').style.display = 'none';
  document.getElementById('info-customer').textContent     = '—';
  document.getElementById('info-address').textContent      = '—';
  document.getElementById('info-date').textContent         = '—';
  document.getElementById('info-agreement').textContent    = '—';
  document.getElementById('landing-input').value           = '';
  document.getElementById('landing-input-excel').value     = '';

  // Reset upload zones
  ['zone-pdf', 'zone-excel'].forEach(id => {
    const z = document.getElementById(id);
    if (z) z.classList.remove('ready', 'active');
  });
  ['zone-pdf-badge', 'zone-excel-badge'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  ['zone-pdf-hint', 'zone-excel-hint'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = '';
  });

  refreshTableVisibility();
}

// ── Download Excel ────────────────────────────────────────────────────────
async function downloadExcel() {
  if (!sessionId) { alert('No active session.'); return; }
  const meta = {
    customer_name: document.getElementById('info-customer').textContent,
    address:       document.getElementById('info-address').textContent,
    checked_by:    '',
    date:          document.getElementById('info-date').textContent,
  };
  const r = await authFetch('/api/generate-excel', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ session_id: sessionId, meta }),
  });
  const data = await r.json();
  const a    = document.createElement('a');
  a.href     = data.download_url;
  a.download = 'QC_Results.xlsx';
  a.click();
}
