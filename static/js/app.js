/* ── API client ──────────────────────────────────────────────────────────── */
const api = {
  async req(method, path, body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
    };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(path, opts);
    const data = await r.json().catch(() => ({}));
    return { ok: r.ok, status: r.status, data };
  },
  get:  (p)    => api.req('GET',  p),
  post: (p, b) => api.req('POST', p, b),
};

/* ── utils ───────────────────────────────────────────────────────────────── */
const $  = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
const el = (tag, cls = '', html = '') => {
  const e = document.createElement(tag);
  if (cls)  e.className = cls;
  if (html) e.innerHTML = html;
  return e;
};

function flash(container, msg, type = 'info') {
  const a = el('div', `alert alert-${type}`, msg);
  container.prepend(a);
  setTimeout(() => a.remove(), 5000);
}

function ts(unix) {
  return new Date(unix * 1000).toLocaleString();
}

function shortHash(h, n = 16) {
  return h ? `${h.slice(0, n)}…` : '—';
}

function copyToClipboard(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'copy'; btn.classList.remove('copied'); }, 1500);
  });
}

/* ── state ───────────────────────────────────────────────────────────────── */
const state = {
  loggedIn: false,
  username: '',
};

/* ── router ──────────────────────────────────────────────────────────────── */
function showPage(id) {
  $$('.page').forEach(p => p.classList.remove('active'));
  $$('.nav-link').forEach(l => l.classList.remove('active'));
  const pg = $(`#page-${id}`);
  if (pg) pg.classList.add('active');
  $$(`[data-page="${id}"]`).forEach(l => l.classList.add('active'));
  window.scrollTo(0, 0);
}

/* ── navbar & auth state ─────────────────────────────────────────────────── */
async function refreshAuthState() {
  const { data } = await api.get('/verifier/me');
  state.loggedIn = data.logged_in;
  state.username = data.username || '';
  const ind = $('#auth-indicator');
  if (ind) {
    ind.className = 'auth-indicator' + (state.loggedIn ? ' logged-in' : '');
    ind.querySelector('.status-dot').className = 'status-dot';
    ind.querySelector('.label').textContent = state.loggedIn
      ? state.username : 'not authenticated';
  }
  renderVerifierPage();
}

async function refreshNodeBar() {
  const { data } = await api.get('/health');
  if (!data.chain_length) return;
  $('#nb-length').textContent = data.chain_length;
  $('#nb-length').className   = 'val ok';
  $('#nb-valid').textContent  = data.chain_valid ? 'valid' : 'INVALID';
  $('#nb-valid').className    = 'val ' + (data.chain_valid ? 'ok' : 'err');
  $('#nb-peers').textContent  = (data.peers || []).length;
  $('#nb-node').textContent   = data.node_url || 'localhost';
}

/* ════════════════════════════════════════════════════════════════════════════
   WALLET PAGE
════════════════════════════════════════════════════════════════════════════ */

function initWalletPage() {
  /* ── create DID ── */
  $('#btn-create-did').addEventListener('click', async function () {
    this.classList.add('btn-loading');
    this.disabled = true;
    const { ok, data } = await api.post('/wallet/create-did');
    this.classList.remove('btn-loading');
    this.disabled = false;

    if (ok) {
      const box = $('#did-result');
      box.classList.remove('hidden');
      const didVal = box.querySelector('.did-value');
      didVal.textContent = data.did;
      const copyBtn = box.querySelector('.copy-btn');
      copyBtn.onclick = () => copyToClipboard(data.did, copyBtn);
      flash($('#wallet-flash'), '✓ DID generated. Save it — it will not be shown again.', 'success');
      refreshNodeBar();
    } else {
      flash($('#wallet-flash'), `Error: ${data.error}`, 'error');
    }
  });

  /* ── view credentials ── */
  $('#btn-view-creds').addEventListener('click', async function () {
    const did = $('#input-view-did').value.trim();
    if (!did) { flash($('#wallet-flash'), 'Enter a DID first.', 'warn'); return; }

    this.classList.add('btn-loading');
    this.disabled = true;
    const { ok, status, data } = await api.get(`/wallet/credentials?did=${encodeURIComponent(did)}`);
    this.classList.remove('btn-loading');
    this.disabled = false;

    renderCredentialResult('#cred-result', data, false);
  });

  /* ── share / QR ── */
  $('#btn-share').addEventListener('click', async function () {
    const did = $('#input-share-did').value.trim();
    if (!did) { flash($('#wallet-flash'), 'Enter a DID to share.', 'warn'); return; }

    this.classList.add('btn-loading');
    this.disabled = true;
    const { ok, data } = await api.get(`/wallet/share?did=${encodeURIComponent(did)}`);
    this.classList.remove('btn-loading');
    this.disabled = false;

    if (ok) {
      const wrap = $('#qr-result');
      wrap.classList.remove('hidden');
      $('#qr-img').src = data.qr_code;
      $('#qr-scan-url').textContent = data.scan_url;
      const copyBtn = $('#btn-copy-qr-url');
      copyBtn.onclick = () => copyToClipboard(data.scan_url, copyBtn);
    } else {
      flash($('#wallet-flash'), `Error: ${data.error}`, 'error');
    }
  });
}

/* ════════════════════════════════════════════════════════════════════════════
   ISSUER PAGE
════════════════════════════════════════════════════════════════════════════ */

function initIssuerPage() {
  /* live hash preview */
  const previewHash = async () => {
    const did  = $('#issue-did').value.trim();
    const name = $('#issue-username').value.trim();
    if (!did || !name) { $('#hash-preview').textContent = '—'; return; }
    const { ok, data } = await api.get(
      `/issuer/verify-hash?did=${encodeURIComponent(did)}&username=${encodeURIComponent(name)}`
    );
    if (ok) {
      $('#hash-preview').textContent = data.verification_hash;
      $('#hash-input-str').textContent = data.input_string;
    }
  };

  $('#issue-did').addEventListener('input', previewHash);
  $('#issue-username').addEventListener('input', previewHash);

  /* issue */
  $('#btn-issue').addEventListener('click', async function () {
    const did      = $('#issue-did').value.trim();
    const username = $('#issue-username').value.trim();
    const degree   = $('#issue-degree').value.trim();
    const expiry   = $('#issue-expiry').value.trim();

    if (!did || !username || !degree || !expiry) {
      flash($('#issuer-flash'), 'All fields are required.', 'warn');
      return;
    }

    this.classList.add('btn-loading');
    this.disabled = true;

    const { ok, data } = await api.post('/issuer/issue', { did, username, degree, expiry });

    this.classList.remove('btn-loading');
    this.disabled = false;

    if (ok) {
      flash($('#issuer-flash'),
        `✓ Block #${data.block.index} mined. Hash: ${shortHash(data.block.hash)}`, 'success');
      $('#issue-did').value = '';
      $('#issue-username').value = '';
      $('#issue-degree').value = '';
      $('#issue-expiry').value = '';
      $('#hash-preview').textContent = '—';
      refreshNodeBar();
      loadChainExplorer();
    } else {
      const msg = data.fields
        ? Object.values(data.fields).join(' | ')
        : data.error;
      flash($('#issuer-flash'), `Error: ${msg}`, 'error');
    }
  });

  loadChainExplorer();
}

async function loadChainExplorer() {
  const { ok, data } = await api.get('/issuer/chain');
  if (!ok) return;

  const tbody = $('#chain-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const blocks = [...data.chain].reverse(); // newest first

  for (const b of blocks) {
    const tr = el('tr', b.block_type.toLowerCase());
    const typeLabel = {
      GENESIS:    `<span class="text-muted">genesis</span>`,
      CREDENTIAL: `<span class="text-green">credential</span>`,
      REVOKE:     `<span class="text-red">revoke</span>`,
    }[b.block_type] || b.block_type;

    const dataStr = b.block_type === 'CREDENTIAL'
      ? `${b.data.username} / ${b.data.degree}`
      : b.block_type === 'REVOKE'
        ? b.data.reason
        : '—';

    tr.innerHTML = `
      <td>${b.index}</td>
      <td>${typeLabel}</td>
      <td title="${b.did}">${b.did === 'GENESIS' ? '—' : shortHash(b.did, 14)}</td>
      <td title="${dataStr}">${dataStr.length > 32 ? dataStr.slice(0,32)+'…' : dataStr}</td>
      <td title="${b.hash}">${shortHash(b.hash, 14)}</td>
      <td>${ts(b.timestamp)}</td>
    `;
    tbody.appendChild(tr);
  }

  $('#chain-length').textContent = data.chain.length;
  $('#chain-valid-badge').className = 'badge ' + (data.valid ? 'badge-valid' : 'badge-invalid');
  $('#chain-valid-badge').textContent = data.valid ? 'valid' : 'invalid';
}

/* ════════════════════════════════════════════════════════════════════════════
   VERIFIER PAGE
════════════════════════════════════════════════════════════════════════════ */

function renderVerifierPage() {
  const gate    = $('#verifier-gate');
  const content = $('#verifier-content');
  if (!gate || !content) return;

  if (state.loggedIn) {
    gate.classList.add('hidden');
    content.classList.remove('hidden');
  } else {
    gate.classList.remove('hidden');
    content.classList.add('hidden');
  }
}

function initVerifierPage() {
  /* gate login form */
  $('#btn-gate-login').addEventListener('click', async function () {
    const username = $('#gate-username').value.trim();
    const password = $('#gate-password').value;
    if (!username || !password) return;

    this.classList.add('btn-loading');
    this.disabled = true;
    const { ok, data } = await api.post('/verifier/login', { username, password });
    this.classList.remove('btn-loading');
    this.disabled = false;

    if (ok) {
      await refreshAuthState();
    } else {
      flash($('#gate-flash'), `Error: ${data.error}`, 'error');
    }
  });

  /* navbar logout */
  $('#btn-logout') && $('#btn-logout').addEventListener('click', async () => {
    await api.post('/verifier/logout');
    await refreshAuthState();
  });

  /* lookup */
  $('#btn-lookup').addEventListener('click', async function () {
    const did = $('#lookup-did').value.trim();
    if (!did) { flash($('#verifier-flash'), 'Enter a DID.', 'warn'); return; }

    this.classList.add('btn-loading');
    this.disabled = true;
    const { ok, status, data } = await api.get(
      `/verifier/lookup?did=${encodeURIComponent(did)}`
    );
    this.classList.remove('btn-loading');
    this.disabled = false;

    renderCredentialResult('#verifier-result', data, true, did);
  });
}

/* ── revoke (wired after render) ── */
async function revokeAction(did) {
  const reason = prompt('Reason for revocation (optional):') || 'Revoked by issuer';
  if (!confirm(`Revoke DID ${did.slice(0, 20)}…?\nThis cannot be undone.`)) return;

  const { ok, data } = await api.post('/verifier/revoke', { did, reason });
  const flashEl = $('#verifier-flash');

  if (ok) {
    flash(flashEl, `✓ DID revoked. Block #${data.block.index} appended.`, 'success');
    $('#btn-lookup').click();
    refreshNodeBar();
    loadChainExplorer();
  } else {
    flash(flashEl, `Error: ${data.error}`, 'error');
  }
}

/* ════════════════════════════════════════════════════════════════════════════
   SHARED: credential result renderer
════════════════════════════════════════════════════════════════════════════ */

function renderCredentialResult(containerSel, data, showRevoke = false, did = '') {
  const container = $(containerSel);
  if (!container) return;
  container.innerHTML = '';
  container.classList.remove('hidden');

  if (data.status === 'not_found') {
    container.innerHTML = `
      <div class="alert alert-warn">
        DID not found on the chain. No credentials have been issued for this identifier.
      </div>`;
    return;
  }

  if (data.status === 'revoked') {
    const ri = data.revoke_info || {};
    let html = `
      <div class="alert alert-error">
        <div>
          <strong>REVOKED</strong><br>
          Reason: ${ri.reason || 'N/A'}<br>
          Revoked at: ${ri.revoked_at ? ts(ri.revoked_at) : 'N/A'}
        </div>
      </div>`;

    if (data.credentials?.length) {
      html += `<p class="text-muted text-mono mt-1" style="font-size:0.72rem;margin-bottom:0.8rem">
        Historical credentials (read-only, chain intact):</p>`;
      for (const c of data.credentials) {
        html += buildCredCard(c, true);
      }
    }
    container.innerHTML = html;
    return;
  }

  /* active */
  const header = el('div', 'flex items-center justify-between mt-1');
  header.style.marginBottom = '1rem';
  header.innerHTML = `
    <div class="flex items-center gap-1">
      <span class="badge badge-active">active</span>
      <span class="text-mono text-muted" style="font-size:0.7rem">${data.credentials.length} credential(s)</span>
    </div>`;

  if (showRevoke && did) {
    const rb = el('button', 'btn btn-danger', 'Revoke DID');
    rb.onclick = () => revokeAction(did || data.did);
    header.appendChild(rb);
  }

  container.appendChild(header);

  for (const c of data.credentials) {
    container.innerHTML += buildCredCard(c, false);
  }
}

function buildCredCard(c, revoked) {
  const hashStatus = c.hash_valid
    ? `<span class="badge badge-valid">hash valid</span>`
    : `<span class="badge badge-invalid">hash mismatch</span>`;

  return `
    <div class="cred-card ${revoked ? 'revoked' : ''}">
      <div class="cred-card-header">
        <div class="cred-degree">${c.degree}</div>
        ${hashStatus}
      </div>
      <div class="cred-meta">
        <div class="cred-field">
          <span class="cred-label">Name</span>
          <span class="cred-value">${c.username}</span>
        </div>
        <div class="cred-field">
          <span class="cred-label">Expiry</span>
          <span class="cred-value">${c.expiry}</span>
        </div>
        <div class="cred-field">
          <span class="cred-label">Issued at</span>
          <span class="cred-value">${ts(c.issued_at)}</span>
        </div>
        <div class="cred-field">
          <span class="cred-label">Block #</span>
          <span class="cred-value">${c.block_index}</span>
        </div>
      </div>
      <div class="cred-hash">
        <span class="cred-label">Verification hash</span><br>
        ${c.verification_hash}
      </div>
    </div>`;
}

/* ── init ─────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  /* nav routing */
  $$('[data-page]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      showPage(link.dataset.page);
    });
  });

  /* dropdown routing */
  $$('[data-page-drop]').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      showPage(item.dataset.pageDrop);
    });
  });

  showPage('wallet');
  initWalletPage();
  initIssuerPage();
  initVerifierPage();
  await refreshAuthState();
  await refreshNodeBar();

  /* auto-refresh node bar every 15s */
  setInterval(refreshNodeBar, 15000);
});
