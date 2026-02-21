/**
 * frontend/js/admin.js
 * Admin panel logic — upload, list, delete, stats (auth-protected).
 */

document.addEventListener('DOMContentLoaded', () => {
    // Guard: admin only
    const user = Auth.requireAuth('admin');
    if (!user) return;
    Auth.populateSidebarUser();

    loadStats();
    loadDocuments();
    initUpload();
});

// ── Stats ────────────────────────────────────────────────────────────────────

async function loadStats() {
    try {
        const res = await fetch('/dashboard/stats', { headers: Auth.authHeaders() });
        if (res.status === 401) { Auth.logout(); return; }
        const data = await res.json();
        animateCounter('stat-docs', data.total_documents ?? 0);
        animateCounter('stat-chunks', data.total_chunks ?? 0);
        animateCounter('stat-queries', data.recent_queries ?? 0);
    } catch (e) {
        console.warn('Stats load failed', e);
    }
}

function animateCounter(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    let current = 0;
    const step = Math.max(1, Math.round(target / 30));
    const timer = setInterval(() => {
        current = Math.min(current + step, target);
        el.textContent = current.toLocaleString();
        if (current >= target) clearInterval(timer);
    }, 30);
}

// ── Documents ────────────────────────────────────────────────────────────────

async function loadDocuments() {
    const tbody = document.getElementById('doc-tbody');
    const label = document.getElementById('doc-count-label');
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><div class="empty-state-icon">⏳</div>Loading…</div></td></tr>`;

    try {
        const res = await fetch('/list-documents', { headers: Auth.authHeaders() });
        if (res.status === 401) { Auth.logout(); return; }
        const data = await res.json();
        const docs = data.documents || [];

        label.textContent = `${docs.length} document${docs.length !== 1 ? 's' : ''} in knowledge base`;

        if (docs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><div class="empty-state-icon">📂</div>No documents yet. Upload your first PDF!</div></td></tr>`;
            return;
        }

        tbody.innerHTML = docs.map(doc => {
            const date = doc.uploaded_at
                ? new Date(doc.uploaded_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
                : '—';
            return `
        <tr>
          <td>
            <div class="doc-name-cell">
              <div class="doc-icon-box">📄</div>
              ${Auth.escapeHtml(doc.source)}
            </div>
          </td>
          <td><span class="chunk-tag">${doc.chunk_count.toLocaleString()} chunks</span></td>
          <td style="color:var(--text-2);font-size:.8rem">${date}</td>
          <td style="text-align:right">
            <button class="btn btn-danger" onclick="deleteDoc('${Auth.escapeHtml(doc.source)}')">
              🗑 Delete
            </button>
          </td>
        </tr>`;
        }).join('');

    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state">⚠ Failed to load documents.</div></td></tr>`;
    }
}

window.deleteDoc = async function (filename) {
    if (!confirm(`Delete "${filename}" and all its embedded chunks?\nThis cannot be undone.`)) return;

    try {
        const res = await fetch(`/delete-document/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
            headers: Auth.authHeaders(),
        });
        if (res.status === 401) { Auth.logout(); return; }
        const data = await res.json();
        if (!res.ok) { Auth.showToast(data.detail || 'Delete failed', 'error'); return; }
        Auth.showToast(`Deleted "${filename}"`, 'success');
        loadDocuments();
        loadStats();
    } catch {
        Auth.showToast('Network error', 'error');
    }
};

// ── Upload ───────────────────────────────────────────────────────────────────

function initUpload() {
    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('file-input');

    // Click on zone triggers file picker
    zone.addEventListener('click', () => input.click());

    // Drag and drop
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        uploadFiles([...e.dataTransfer.files].filter(f => f.name.endsWith('.pdf')));
    });

    input.addEventListener('change', () => {
        uploadFiles([...input.files]);
        input.value = '';
    });
}

async function uploadFiles(files) {
    if (!files.length) { Auth.showToast('Please select PDF files only.', 'error'); return; }

    const progressWrap = document.getElementById('upload-progress');
    const progressLabel = document.getElementById('upload-progress-label');
    progressWrap.style.display = 'flex';

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        progressLabel.textContent = `Uploading ${i + 1}/${files.length}: ${file.name}`;

        const fd = new FormData();
        fd.append('file', file);

        try {
            const res = await fetch('/upload-documents', {
                method: 'POST',
                headers: Auth.authHeaders(),
                body: fd,
            });
            if (res.status === 401) { Auth.logout(); return; }
            const data = await res.json();
            if (!res.ok) {
                Auth.showToast(`Failed: ${data.detail || file.name}`, 'error');
            } else {
                Auth.showToast(`✓ ${file.name} — ${data.chunks_ingested} chunks`, 'success');
            }
        } catch {
            Auth.showToast(`Network error uploading ${file.name}`, 'error');
        }
    }

    progressWrap.style.display = 'none';
    loadDocuments();
    loadStats();
}

// Expose for sidebar refresh button
window.loadStats = loadStats;
window.loadDocuments = loadDocuments;
