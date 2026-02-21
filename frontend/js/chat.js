/**
 * frontend/js/chat.js
 * Chat interface logic — sends auth headers with every request.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Guard: must be logged in
  const user = Auth.requireAuth();
  if (!user) return;
  Auth.populateSidebarUser();

  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const messages = document.getElementById('messages');
  const welcome = document.getElementById('welcome');

  // Enable send when there is text
  input.addEventListener('input', () => {
    sendBtn.disabled = !input.value.trim();
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  // Send on Enter (Shift+Enter = newline)
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) sendMessage();
    }
  });

  sendBtn.addEventListener('click', sendMessage);

  async function sendMessage() {
    const question = input.value.trim();
    if (!question) return;

    // Hide welcome state
    if (welcome) welcome.style.display = 'none';

    // Render user message
    appendUserMessage(question);
    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;

    // Thinking indicator
    const thinkingEl = appendThinking();

    try {
      const res = await fetch('/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...Auth.authHeaders(),
        },
        body: JSON.stringify({ question }),
      });

      thinkingEl.remove();

      if (res.status === 401) {
        Auth.logout();
        return;
      }

      const data = await res.json();

      if (!res.ok) {
        appendBotMessage(`⚠ ${data.detail || 'An error occurred.'}`, [], 0);
        return;
      }

      appendBotMessage(data.answer, data.citations || [], data.confidence_score || 0, data.retrieved_chunks);

    } catch (err) {
      thinkingEl.remove();
      Auth.showToast('Network error. Please try again.', 'error');
    }
  }

  function appendUserMessage(text) {
    const user = Auth.getUser();
    const initial = (user?.display_name || 'U').charAt(0).toUpperCase();

    const div = document.createElement('div');
    div.className = 'msg user';
    div.innerHTML = `
      <div class="msg-av">${Auth.escapeHtml(initial)}</div>
      <div class="msg-body">
        <div class="msg-bubble">${Auth.escapeHtml(text)}</div>
      </div>`;
    messages.appendChild(div);
    scrollBottom();
  }

  function appendThinking() {
    const div = document.createElement('div');
    div.className = 'msg bot';
    div.innerHTML = `
      <div class="msg-av">🧠</div>
      <div class="msg-body">
        <div class="thinking">
          <div class="dot"></div><div class="dot"></div><div class="dot"></div>
        </div>
      </div>`;
    messages.appendChild(div);
    scrollBottom();
    return div;
  }

  function appendBotMessage(answer, citations, confidence, chunks) {
    const isFallback = !citations || citations.length === 0;
    const pct = Math.round((confidence || 0) * 100);
    const confColor = pct >= 80 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444';

    let citHtml = '';
    if (!isFallback && citations.length > 0) {
      const pills = citations.map(c =>
        `<span class="citation-pill">📄 ${Auth.escapeHtml(c.source)} · p.${c.page}</span>`
      ).join('');
      citHtml = `
        <div class="citations">
          <div class="citations-label">Sources</div>
          <div>${pills}</div>
          <div class="conf-row">
            <span>Confidence</span>
            <div class="conf-track"><div class="conf-fill" style="width:${pct}%;background:${confColor}"></div></div>
            <span style="color:${confColor};font-weight:600">${pct}%</span>
            ${chunks ? `<span>· ${chunks} chunk${chunks !== 1 ? 's' : ''} searched</span>` : ''}
          </div>
        </div>`;
    }

    const div = document.createElement('div');
    div.className = 'msg bot';
    div.innerHTML = `
      <div class="msg-av">🧠</div>
      <div class="msg-body">
        <div class="msg-bubble">${Auth.escapeHtml(answer)}</div>
        ${citHtml}
      </div>`;
    messages.appendChild(div);
    scrollBottom();
  }

  function scrollBottom() {
    messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });
  }

  // Quick chip handler
  window.useChip = function (btn) {
    input.value = btn.textContent.replace(/^[^\w]+/, '').trim();
    input.dispatchEvent(new Event('input'));
    sendMessage();
  };
});
