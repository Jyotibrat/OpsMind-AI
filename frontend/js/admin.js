/**
 * frontend/js/admin.js
 * Admin panel logic: upload PDFs, list/delete documents, view stats
 */

const API_BASE = window.location.origin;

// ── State ─────────────────────────────────────────────────────────────────────
let currentDocuments = [];

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadDocuments();
    initUploadZone();
});

// ── Stats ─────────────────────────────────────────────────────────────────────
async function loadStats() {
    try {
        const res = await fetch(`${API_BASE}/dashboard/stats`);
        if (!res.ok) throw new Error('Stats unavailable');
        const data = await res.json();

        setStatValue('stat-docs', data.total_documents ?? 0);
        setStatValue('stat-chunks', data.total_chunks ?? 0);
        setStatValue('stat-queries', data.recent_queries ?? 0);
    } catch {
        ['stat-docs', 'stat-chunks', 'stat-queries'].forEach(id => setStatValue(id, '—'));
    }
}

function setStatValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

// ── Upload Zone ───────────────────────────────────────────────────────────────
function initUploadZone() {
    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('file-input');
    const progress = document.getElementById('upload-progress');
    const progressText = document.getElementById('progress-text');

    // Drag & drop
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('dragover');
        handleFiles(Array.from(e.dataTransfer.files));
    });

    input.addEventListener('change', () => handleFiles(Array.from(input.files || [])));

    async function handleFiles(files) {
        const pdfs = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
        if (pdfs.length === 0) {
            showToast('Please upload PDF files only.', 'error');
            return;
        }

        progress.style.display = 'flex';

        for (const file of pdfs) {
            if (progressText) progressText.textContent = `Uploading ${file.name}…`;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch(`${API_BASE}/upload-documents`, {
                    method: 'POST',
                    body: formData,
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
                showToast(`✓ ${file.name} — ${data.chunks_ingested} chunks ingested`, 'success');
            } catch (err) {
                showToast(`✗ ${file.name}: ${err.message}`, 'error');
            }
        }

        progress.style.display = 'none';
        input.value = '';
        await loadStats();
        await loadDocuments();
    }
}

// ── Load Document List ────────────────────────────────────────────────────────
async function loadDocuments() {
    const tbody = document.getElementById('doc-tbody');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="4" class="empty-state"><div class="empty-state-icon">⏳</div>Loading…</td></tr>`;

    try {
        const res = await fetch(`${API_BASE}/list-documents`);
        if (!res.ok) throw new Error('Failed to load documents');
        const data = await res.json();
        currentDocuments = data.documents || [];
        renderDocumentTable(currentDocuments);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="4" class="empty-state">
      <div class="empty-state-icon">⚠️</div>
      <div>Failed to load documents: ${escapeHtml(err.message)}</div>
    </td></tr>`;
    }
}

function renderDocumentTable(documents) {
    const tbody = document.getElementById('doc-tbody');
    const countEl = document.getElementById('doc-count');
    if (countEl) countEl.textContent = documents.length;

    if (documents.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4">
      <div class="empty-state">
        <div class="empty-state-icon">📂</div>
        <div>No documents ingested yet. Upload a PDF above to get started.</div>
      </div>
    </td></tr>`;
        return;
    }

    tbody.innerHTML = documents.map((doc, idx) => {
        const uploadedAt = doc.uploaded_at
            ? new Date(doc.uploaded_at).toLocaleString()
            : '—';
        return `
      <tr>
        <td>
          <div class="doc-name">
            <div class="doc-icon">📄</div>
            <span>${escapeHtml(doc.source)}</span>
          </div>
        </td>
        <td><span class="chunk-badge">${doc.chunk_count} chunks</span></td>
        <td style="color: var(--text-secondary); font-size: 0.8rem;">${uploadedAt}</td>
        <td>
          <button class="btn btn-danger" onclick="deleteDocument('${escapeAttr(doc.source)}')">
            🗑 Delete
          </button>
        </td>
      </tr>
    `;
    }).join('');
}

// ── Delete Document ───────────────────────────────────────────────────────────
async function deleteDocument(filename) {
    if (!confirm(`Delete "${filename}" and all its chunks? This cannot be undone.`)) return;

    try {
        const res = await fetch(`${API_BASE}/delete-document/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

        showToast(`Deleted "${filename}" (${data.deleted_chunks} chunks removed)`, 'success');
        await loadStats();
        await loadDocuments();
    } catch (err) {
        showToast(`Delete failed: ${err.message}`, 'error');
    }
}

window.deleteDocument = deleteDocument;

// ── Refresh ───────────────────────────────────────────────────────────────────
document.getElementById('refresh-btn')?.addEventListener('click', async () => {
    await loadStats();
    await loadDocuments();
    showToast('Refreshed', 'info');
});

// ── Utilities ─────────────────────────────────────────────────────────────────
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeAttr(str) {
    return String(str).replace(/'/g, "\\'");
}

function showToast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = { success: '✓', error: '✗', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${escapeHtml(msg)}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}
