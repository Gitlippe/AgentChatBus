/**
 * Vitest tests for UP-21: message edit/versioning UI behaviour.
 *
 * Strategy: the edit functions (AcbMsgEditStart, AcbMsgEditCancel, AcbMsgEditHistory)
 * are defined inline in index.html and assigned to window.*. We replicate the core
 * DOM setup and mock the external dependencies (api, AcbMessageRenderer) to test
 * the logic without loading the full page.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildMessageRow({ msgId = 'msg-001', author = 'agent-a', editedAt = null, editVersion = 0 } = {}) {
  const row = document.createElement('div');
  row.className = 'msg-row msg-row-left';
  row.setAttribute('data-msg-id', msgId);
  row.setAttribute('data-seq', '1');

  row.innerHTML = `
    <div class="msg-col">
      <div class="msg-header">
        <span class="msg-author-label">${author}</span>
        <button class="msg-edit-btn toolbar-btn"
          data-msg-id="${msgId}"
          data-author="${author}">✏️</button>
      </div>
      <div class="bubble-v2">Original message content</div>
      ${editedAt ? `<span class="msg-edited-indicator" data-msg-id="${msgId}">edited</span>` : ''}
      <div class="msg-reactions"></div>
    </div>`;

  document.body.appendChild(row);
  return row;
}

// Install minimal window globals used by the edit functions
function installGlobals(apiFn) {
  window.AcbMessageRenderer = {
    renderMessageContent: vi.fn((el, text) => { el.textContent = text; }),
  };
  window.api = apiFn || vi.fn(() => Promise.resolve({}));

  // Install AcbMsgEditStart — copy of the production logic under test
  window.AcbMsgEditStart = function(btn) {
    const row = btn.closest('.msg-row');
    if (!row) return;
    const msgId = btn.getAttribute('data-msg-id');
    const author = btn.getAttribute('data-author');
    const bubbleEl = row.querySelector('.bubble-v2');
    if (!bubbleEl || row.classList.contains('msg-editing')) return;

    row.classList.add('msg-editing');
    btn.disabled = true;

    const originalContent = bubbleEl.innerText || bubbleEl.textContent;
    bubbleEl.dataset.originalContent = originalContent;

    const textarea = document.createElement('textarea');
    textarea.className = 'msg-edit-textarea';
    textarea.value = originalContent;

    const actions = document.createElement('div');
    actions.className = 'msg-edit-actions';

    const saveBtn = document.createElement('button');
    saveBtn.className = 'msg-edit-save-btn';
    saveBtn.textContent = 'Save';
    saveBtn.onclick = async () => {
      const newContent = textarea.value.trim();
      if (!newContent) return;
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving…';
      try {
        const resp = await window.api(`/api/messages/${msgId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: newContent, edited_by: author }),
        });
        if (resp.no_change) { window.AcbMsgEditCancel(row); return; }
        bubbleEl.innerHTML = '';
        window.AcbMessageRenderer.renderMessageContent(bubbleEl, newContent, null);
        let indicator = row.querySelector('.msg-edited-indicator');
        if (!indicator) {
          indicator = document.createElement('span');
          indicator.className = 'msg-edited-indicator';
          indicator.setAttribute('data-msg-id', msgId);
          indicator.setAttribute('onclick', 'window.AcbMsgEditHistory(this)');
          const reactions = row.querySelector('.msg-reactions');
          if (reactions) reactions.before(indicator);
        }
        indicator.title = `Edited (v${resp.version})`;
        indicator.textContent = 'edited';
        window.AcbMsgEditCancel(row);
      } catch (err) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
      }
    };

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'msg-edit-cancel-btn';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.onclick = () => window.AcbMsgEditCancel(row);

    actions.appendChild(saveBtn);
    actions.appendChild(cancelBtn);
    bubbleEl.innerHTML = '';
    bubbleEl.appendChild(textarea);
    bubbleEl.appendChild(actions);
    textarea.focus();
  };

  window.AcbMsgEditCancel = function(row) {
    if (!row) return;
    row.classList.remove('msg-editing');
    const editBtn = row.querySelector('.msg-edit-btn');
    if (editBtn) editBtn.disabled = false;
    const bubbleEl = row.querySelector('.bubble-v2');
    if (!bubbleEl) return;
    const original = bubbleEl.dataset.originalContent || '';
    bubbleEl.innerHTML = '';
    window.AcbMessageRenderer.renderMessageContent(bubbleEl, original, null);
    delete bubbleEl.dataset.originalContent;
  };

  window.AcbMsgEditHistory = async function(el) {
    const msgId = el.getAttribute('data-msg-id');
    if (!msgId) return;
    const data = await window.api(`/api/messages/${msgId}/history`);

    const modal = document.createElement('div');
    modal.id = 'edit-history-modal-test';
    modal.className = 'msg-edit-history-modal';
    document.body.appendChild(modal);

    if (!data.edits || data.edits.length === 0) {
      const p = document.createElement('p');
      p.textContent = 'No edit history.';
      modal.appendChild(p);
    } else {
      data.edits.forEach(edit => {
        const entry = document.createElement('div');
        entry.className = 'msg-edit-history-entry';
        entry.textContent = edit.old_content;
        modal.appendChild(entry);
      });
    }
    return modal;
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('UP-21: msg-edit-btn', () => {
  beforeEach(() => { installGlobals(); });
  afterEach(() => { document.body.innerHTML = ''; vi.clearAllMocks(); });

  it('edit button exists on a message row', () => {
    const row = buildMessageRow();
    const btn = row.querySelector('.msg-edit-btn');
    expect(btn).not.toBeNull();
    expect(btn.getAttribute('data-msg-id')).toBe('msg-001');
  });

  it('edit button carries the author attribute', () => {
    const row = buildMessageRow({ author: 'agent-x' });
    const btn = row.querySelector('.msg-edit-btn');
    expect(btn.getAttribute('data-author')).toBe('agent-x');
  });
});

describe('UP-21: AcbMsgEditStart', () => {
  beforeEach(() => { installGlobals(); });
  afterEach(() => { document.body.innerHTML = ''; vi.clearAllMocks(); });

  it('clicking edit replaces bubble with textarea', () => {
    const row = buildMessageRow();
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);

    const textarea = row.querySelector('.msg-edit-textarea');
    expect(textarea).not.toBeNull();
    expect(textarea.value).toBe('Original message content');
  });

  it('clicking edit adds Save and Cancel buttons', () => {
    const row = buildMessageRow();
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);

    expect(row.querySelector('.msg-edit-save-btn')).not.toBeNull();
    expect(row.querySelector('.msg-edit-cancel-btn')).not.toBeNull();
  });

  it('clicking edit disables the edit button', () => {
    const row = buildMessageRow();
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);

    expect(btn.disabled).toBe(true);
  });

  it('calling AcbMsgEditStart twice (msg-editing guard) is idempotent', () => {
    const row = buildMessageRow();
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);
    window.AcbMsgEditStart(btn); // second call should no-op

    const textareas = row.querySelectorAll('.msg-edit-textarea');
    expect(textareas.length).toBe(1); // still just one textarea
  });
});

describe('UP-21: AcbMsgEditCancel', () => {
  beforeEach(() => { installGlobals(); });
  afterEach(() => { document.body.innerHTML = ''; vi.clearAllMocks(); });

  it('cancel restores original bubble content', () => {
    const row = buildMessageRow();
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);
    window.AcbMsgEditCancel(row);

    expect(row.querySelector('.msg-edit-textarea')).toBeNull();
    expect(window.AcbMessageRenderer.renderMessageContent).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      'Original message content',
      null
    );
  });

  it('cancel re-enables the edit button', () => {
    const row = buildMessageRow();
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);
    window.AcbMsgEditCancel(row);

    expect(btn.disabled).toBe(false);
  });

  it('cancel removes msg-editing class from row', () => {
    const row = buildMessageRow();
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);
    expect(row.classList.contains('msg-editing')).toBe(true);

    window.AcbMsgEditCancel(row);
    expect(row.classList.contains('msg-editing')).toBe(false);
  });
});

describe('UP-21: Save edit', () => {
  afterEach(() => { document.body.innerHTML = ''; vi.clearAllMocks(); });

  it('save calls api PUT with correct payload', async () => {
    const apiFn = vi.fn(() => Promise.resolve({ msg_id: 'msg-001', version: 1, edited_at: 'now' }));
    installGlobals(apiFn);
    const row = buildMessageRow({ msgId: 'msg-001', author: 'agent-a' });
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);
    const textarea = row.querySelector('.msg-edit-textarea');
    textarea.value = 'edited content';

    const saveBtn = row.querySelector('.msg-edit-save-btn');
    await saveBtn.onclick();

    expect(apiFn).toHaveBeenCalledWith(
      '/api/messages/msg-001',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('save adds edited indicator after successful save', async () => {
    const apiFn = vi.fn(() => Promise.resolve({ msg_id: 'msg-001', version: 1, edited_at: 'now' }));
    installGlobals(apiFn);
    const row = buildMessageRow({ msgId: 'msg-001', author: 'agent-a' });
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);
    row.querySelector('.msg-edit-textarea').value = 'new text';

    await row.querySelector('.msg-edit-save-btn').onclick();

    const indicator = row.querySelector('.msg-edited-indicator');
    expect(indicator).not.toBeNull();
    expect(indicator.textContent).toBe('edited');
  });

  it('no_change response cancels editing without creating indicator', async () => {
    const apiFn = vi.fn(() => Promise.resolve({ no_change: true, version: 0 }));
    installGlobals(apiFn);
    const row = buildMessageRow({ msgId: 'msg-001', author: 'agent-a' });
    const btn = row.querySelector('.msg-edit-btn');

    window.AcbMsgEditStart(btn);
    row.querySelector('.msg-edit-textarea').value = 'Original message content';

    await row.querySelector('.msg-edit-save-btn').onclick();

    expect(row.classList.contains('msg-editing')).toBe(false);
    expect(row.querySelector('.msg-edited-indicator')).toBeNull();
  });
});

describe('UP-21: edited indicator', () => {
  beforeEach(() => { installGlobals(); });
  afterEach(() => { document.body.innerHTML = ''; vi.clearAllMocks(); });

  it('"edited" indicator is present when editedAt is truthy', () => {
    const row = buildMessageRow({ editedAt: '2026-03-03T12:00:00Z' });
    const indicator = row.querySelector('.msg-edited-indicator');
    expect(indicator).not.toBeNull();
    expect(indicator.textContent).toBe('edited');
  });

  it('"edited" indicator is absent when editedAt is null', () => {
    const row = buildMessageRow({ editedAt: null });
    const indicator = row.querySelector('.msg-edited-indicator');
    expect(indicator).toBeNull();
  });
});

describe('UP-21: AcbMsgEditHistory', () => {
  afterEach(() => { document.body.innerHTML = ''; vi.clearAllMocks(); });

  it('history modal shows edit entries', async () => {
    const historyData = {
      message_id: 'msg-001',
      current_content: 'final',
      edit_version: 2,
      edits: [
        { version: 1, old_content: 'v0', edited_by: 'agent-a', created_at: '2026-01-01T00:00:00Z' },
        { version: 2, old_content: 'v1', edited_by: 'agent-a', created_at: '2026-01-02T00:00:00Z' },
      ],
    };
    const apiFn = vi.fn(() => Promise.resolve(historyData));
    installGlobals(apiFn);

    const indicator = document.createElement('span');
    indicator.className = 'msg-edited-indicator';
    indicator.setAttribute('data-msg-id', 'msg-001');
    document.body.appendChild(indicator);

    const modal = await window.AcbMsgEditHistory(indicator);

    expect(apiFn).toHaveBeenCalledWith('/api/messages/msg-001/history');
    const entries = modal.querySelectorAll('.msg-edit-history-entry');
    expect(entries.length).toBe(2);
  });

  it('history modal shows "No edit history." when edits array is empty', async () => {
    const historyData = { message_id: 'msg-001', current_content: 'text', edit_version: 0, edits: [] };
    const apiFn = vi.fn(() => Promise.resolve(historyData));
    installGlobals(apiFn);

    const indicator = document.createElement('span');
    indicator.setAttribute('data-msg-id', 'msg-001');
    document.body.appendChild(indicator);

    const modal = await window.AcbMsgEditHistory(indicator);

    expect(modal.querySelector('p').textContent).toContain('No edit history');
  });
});
