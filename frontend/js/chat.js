/**
 * frontend/js/chat.js
 * Chat page logic for OpsMind AI employee Q&A interface
 */

const API_BASE = window.location.origin;

const chatMessages  = document.getElementById('chat-messages');
const chatInput     = document.getElementById('chat-input');
const sendBtn       = document.getElementById('send-btn');
const welcomeState  = document.getElementById('welcome-state');

let isLoading = false;

// ── Quick Chips ──────────────────────────────────────────────────────────────
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    chatInput.value = chip.dataset.q;
    chatInput.dispatchEvent(new Event('input'));
    sendMessage();
  });
});

// ── Auto-resize textarea ──────────────────────────────────────────────────────
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  sendBtn.disabled = !chatInput.value.trim() || isLoading;
});

// ── Enter to send (Shift+Enter for newline) ────────────────────────────────────
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage();
  }
});

sendBtn.addEventListener('click', sendMessage);

// ── Send Message ──────────────────────────────────────────────────────────────
async function sendMessage() {
  const question = chatInput.value.trim();
  if (!question || isLoading) return;

  // Hide welcome state on first message
  if (welcomeState) welcomeState.style.display = 'none';

  // Append user bubble
  appendMessage('user', question);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;
  isLoading = true;

  // Show thinking bubble
  const thinkingEl = appendThinking();

  try {
    const res = await fetch(`${API_BASE}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    thinkingEl.remove();
    appendAssistantMessage(data);

  } catch (err) {
    thinkingEl.remove();
    appendMessage('assistant', `⚠️ Error: ${err.message}`, true);
    showToast(`Request failed: ${err.message}`, 'error');
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

// ── Append User / Simple Bubble ────────────────────────────────────────────────
function appendMessage(role, text, isError = false) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'user' ? '👤' : '🤖';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  if (isError) bubble.style.color = 'var(--danger)';
  bubble.textContent = text;

  div.appendChild(avatar);
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

// ── Thinking Bubble ────────────────────────────────────────────────────────────
function appendThinking() {
  const div = document.createElement('div');
  div.className = 'message assistant';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = '🤖';

  const bubble = document.createElement('div');
  bubble.className = 'thinking-bubble';
  bubble.innerHTML = `
    <span class="dot-bounce"></span>
    <span class="dot-bounce"></span>
    <span class="dot-bounce"></span>
  `;

  div.appendChild(avatar);
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

// ── Append Full Assistant Response ─────────────────────────────────────────────
function appendAssistantMessage(data) {
  const div = document.createElement('div');
  div.className = 'message assistant';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = '🤖';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  // Answer text (render line breaks)
  const answerP = document.createElement('div');
  answerP.style.whiteSpace = 'pre-wrap';
  answerP.textContent = data.answer;
  bubble.appendChild(answerP);

  // Citations block
  if (data.citations && data.citations.length > 0) {
    const citBlock = document.createElement('div');
    citBlock.className = 'citations-block';

    const label = document.createElement('div');
    label.className = 'citations-label';
    label.textContent = '📚 Sources';
    citBlock.appendChild(label);

    const tagsWrap = document.createElement('div');
    data.citations.forEach(cit => {
      const tag = document.createElement('span');
      tag.className = 'citation-tag';
      tag.innerHTML = `📄 ${escapeHtml(cit.source)} · p.${cit.page}`;
      tagsWrap.appendChild(tag);
    });
    citBlock.appendChild(tagsWrap);

    // Confidence bar
    const conf = data.confidence_score || 0;
    const barWrap = document.createElement('div');
    barWrap.className = 'confidence-bar-wrap';
    barWrap.innerHTML = `
      <span>Confidence</span>
      <div class="confidence-bar">
        <div class="confidence-fill" style="width: ${Math.round(conf * 100)}%"></div>
      </div>
      <span>${Math.round(conf * 100)}%</span>
    `;
    citBlock.appendChild(barWrap);
    bubble.appendChild(citBlock);
  }

  div.appendChild(avatar);
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  scrollToBottom();
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Toast (shared) ────────────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = { success: '✓', error: '✗', info: 'ℹ' };
  toast.innerHTML = `<span>${icons[type]}</span><span>${escapeHtml(msg)}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

window.showToast = showToast;
