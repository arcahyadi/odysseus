/**
 * persona-switcher.js — Persona dropdown in the chat header.
 * Requirements: 4.7
 */

export class PersonaSwitcher {
  /**
   * @param {string} sessionId
   * @param {HTMLElement} headerEl - element containing a .persona-slot child
   */
  constructor(sessionId, headerEl) {
    this.sessionId = sessionId;
    this.headerEl = headerEl;
    this._selectEl = null;
    this._currentName = null;
    this._render();
  }

  /** Return the display name of the currently active persona, or null. */
  getCurrentPersonaName() {
    return this._currentName;
  }

  // ── Private ──────────────────────────────────────────────────────────────

  async _render() {
    try {
      const res = await fetch('/api/personas');
      if (!res.ok) return;
      const { personas } = await res.json();

      const slot = this.headerEl.querySelector('.persona-slot');
      if (!slot) return;

      const sel = document.createElement('select');
      sel.className = 'persona-select';
      sel.setAttribute('aria-label', 'Active persona');

      const blank = document.createElement('option');
      blank.value = '';
      blank.textContent = '— No Persona —';
      sel.appendChild(blank);

      (personas || []).forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name + (p.is_builtin ? ' 🔒' : '');
        sel.appendChild(opt);
      });

      sel.addEventListener('change', () => this._onSelect(sel.value, personas));
      this._selectEl = sel;
      slot.replaceChildren(sel);

      // Sync current state from the session
      await this._syncState(personas);
    } catch (err) {
      console.warn('PersonaSwitcher render failed:', err);
    }
  }

  async _syncState(personas) {
    try {
      const res = await fetch(`/api/sessions/${this.sessionId}/persona`);
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.id && this._selectEl) {
        this._selectEl.value = data.id;
        this._currentName = data.name || null;
        this._updateHeader();
      }
    } catch (_) { /* ignore */ }
  }

  async _onSelect(personaId, personas) {
    if (!personaId) {
      await this._deactivate();
    } else {
      await this._activate(personaId);
      const found = (personas || []).find(p => p.id === personaId);
      this._currentName = found ? found.name : null;
    }
    this._updateHeader();
  }

  async _activate(personaId) {
    try {
      await fetch(`/api/sessions/${this.sessionId}/persona`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ persona_id: personaId }),
      });
    } catch (err) {
      console.warn('PersonaSwitcher activate failed:', err);
    }
  }

  async _deactivate() {
    this._currentName = null;
    try {
      await fetch(`/api/sessions/${this.sessionId}/persona`, { method: 'DELETE' });
    } catch (err) {
      console.warn('PersonaSwitcher deactivate failed:', err);
    }
  }

  _updateHeader() {
    const badge = this.headerEl.querySelector('.persona-badge');
    if (!badge) return;
    if (this._currentName) {
      badge.textContent = this._currentName;
      badge.hidden = false;
    } else {
      badge.textContent = '';
      badge.hidden = true;
    }
  }
}
