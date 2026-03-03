(function registerAcbThreadHeader() {
  class AcbThreadHeader extends HTMLElement {
    connectedCallback() {
      if (this.childElementCount > 0) return;

      this.innerHTML = `
        <div id="thread-header" style="display:none">
          <h2 id="thread-title"></h2>
          <div style="display:flex;gap:8px;align-items:center;">
            <button id="search-toggle-btn" type="button" title="Search messages (Ctrl+F)" aria-label="Search messages" onclick="window.AcbSearch && window.AcbSearch.toggle()">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </button>
            <button id="export-thread-btn" type="button" title="Export as Markdown" aria-label="Export thread as Markdown" onclick="exportFromHeader()">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 1v9M4.5 6.5 8 10l3.5-3.5M2 11v2.5A1.5 1.5 0 0 0 3.5 15h9A1.5 1.5 0 0 0 14 13.5V11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button id="thread-settings-btn" type="button" title="Thread Settings" aria-label="Thread settings" onclick="openThreadSettingsModal()" style="background:transparent;border:none;cursor:pointer;font-size:16px;padding:4px;display:flex;align-items:center;justify-content:center;width:24px;height:24px;">⚙️</button>
          </div>
          <div id="online-presence" title="">
            <span id="online-count">1</span>
          </div>
        </div>`;
    }
  }

  if (!customElements.get('acb-thread-header')) {
    customElements.define('acb-thread-header', AcbThreadHeader);
  }
})();
