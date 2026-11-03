/**
 * docStepBuilder.js — UI for creating document-aware plan steps.
 * Allows users to select a document and choose an action (create/update/edit/suggest/read).
 */

const PLANS_API = '/api/plans';

export class DocStepBuilder {
  /**
   * @param {string} planId - The plan to add the step to
   * @param {string} planTitle - The plan title for display
   */
  constructor(planId, planTitle) {
    this.planId = planId;
    this.planTitle = planTitle;
    this.overlay = null;
  }

  async open() {
    if (this.overlay) {
      this.overlay.remove();
    }
    
    const overlay = document.createElement('div');
    overlay.className = 'modal p2-doc-step-modal';
    overlay.id = 'p2-doc-step-overlay';
    
    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.width = '600px';
    
    const header = document.createElement('div');
    header.className = 'modal-header';
    header.innerHTML = '<h4>Add Document Step</h4>';
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-btn';
    closeBtn.setAttribute('aria-label', 'Close document step builder');
    closeBtn.innerHTML = '&#x2716;';
    closeBtn.addEventListener('click', () => {
      overlay.remove();
      if (this.overlay === overlay) {
        this.overlay = null;
      }
    });
    header.appendChild(closeBtn);
    content.appendChild(header);
    
    const body = document.createElement('div');
    body.className = 'modal-body';
    body.style.padding = '16px';
    
    // Form for document step
    const form = document.createElement('form');
    form.style.cssText = 'display:flex;flex-direction:column;gap:12px;';
    
    // Plan info
    const planInfo = document.createElement('div');
    planInfo.style.cssText = 'background:color-mix(in srgb, var(--bg) 80%, var(--accent) 20%);padding:8px;border-radius:6px;font-size:0.9em;';
    planInfo.innerHTML = `<strong>Plan:</strong> ${this.planTitle}`;
    form.appendChild(planInfo);
    
    // Title field
    const titleGroup = document.createElement('div');
    titleGroup.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
    const titleLabel = document.createElement('label');
    titleLabel.htmlFor = 'p2-doc-step-title';
    titleLabel.textContent = 'Step title';
    titleLabel.style.cssText = 'font-weight:600;';
    const titleInput = document.createElement('input');
    titleInput.id = 'p2-doc-step-title';
    titleInput.type = 'text';
    titleInput.required = true;
    titleInput.placeholder = 'e.g., Research market trends';
    titleInput.style.cssText = 'padding:8px;border:1px solid var(--border);border-radius:4px;font-size:1em;';
    titleGroup.appendChild(titleLabel);
    titleGroup.appendChild(titleInput);
    form.appendChild(titleGroup);
    
    // Document selector
    const docGroup = document.createElement('div');
    docGroup.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
    const docLabel = document.createElement('label');
    docLabel.htmlFor = 'p2-doc-step-doc';
    docLabel.textContent = 'Target document';
    docLabel.style.cssText = 'font-weight:600;';
    const docSelect = document.createElement('select');
    docSelect.id = 'p2-doc-step-doc';
    docSelect.required = true;
    docSelect.style.cssText = 'padding:8px;border:1px solid var(--border);border-radius:4px;font-size:1em;';
    docGroup.appendChild(docLabel);
    docGroup.appendChild(docSelect);
    form.appendChild(docGroup);
    
    // Action selector
    const actionGroup = document.createElement('div');
    actionGroup.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
    const actionLabel = document.createElement('label');
    actionLabel.htmlFor = 'p2-doc-step-action';
    actionLabel.textContent = 'Action';
    actionLabel.style.cssText = 'font-weight:600;';
    const actionSelect = document.createElement('select');
    actionSelect.id = 'p2-doc-step-action';
    actionSelect.required = true;
    actionSelect.style.cssText = 'padding:8px;border:1px solid var(--border);border-radius:4px;font-size:1em;';
    const actions = [
      { value: 'create', label: 'Create (new document)' },
      { value: 'update', label: 'Update (replace content)' },
      { value: 'edit', label: 'Edit (FIND/REPLACE blocks)' },
      { value: 'suggest', label: 'Suggest (review mode)' },
      { value: 'read', label: 'Read (view document)' },
    ];
    actions.forEach(a => {
      const opt = document.createElement('option');
      opt.value = a.value;
      opt.textContent = a.label;
      actionSelect.appendChild(opt);
    });
    actionGroup.appendChild(actionLabel);
    actionGroup.appendChild(actionSelect);
    form.appendChild(actionGroup);
    
    // Description field (for create/update/edit actions)
    const descGroup = document.createElement('div');
    descGroup.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
    const descLabel = document.createElement('label');
    descLabel.htmlFor = 'p2-doc-step-desc';
    descLabel.textContent = 'Description / Content';
    descLabel.style.cssText = 'font-weight:600;';
    const descTextarea = document.createElement('textarea');
    descTextarea.id = 'p2-doc-step-desc';
    descTextarea.rows = 3;
    descTextarea.placeholder = 'For "Create": initial content or title\nFor "Update/Edit": full content or FIND/REPLACE blocks';
    descTextarea.style.cssText = 'padding:8px;border:1px solid var(--border);border-radius:4px;font-size:1em;font-family:monospace;';
    descGroup.appendChild(descLabel);
    descGroup.appendChild(descTextarea);
    form.appendChild(descGroup);
    
    // Help text for each action
    const helpText = document.createElement('div');
    helpText.id = 'p2-doc-step-help';
    helpText.style.cssText = 'font-size:0.85em;color:color-mix(in srgb, var(--fg) 65%, transparent);padding:8px;background:color-mix(in srgb, var(--bg) 90%, var(--accent) 10%);border-radius:4px;';
    helpText.textContent = 'Create: Creates a new document with the provided content.';
    form.appendChild(helpText);
    
    // Buttons
    const btnGroup = document.createElement('div');
    btnGroup.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;margin-top:8px;';
    
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn-secondary';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.style.cssText = 'padding:8px 16px;';
    cancelBtn.addEventListener('click', () => {
      overlay.remove();
    });
    
    const createBtn = document.createElement('button');
    createBtn.type = 'submit';
    createBtn.className = 'btn-primary';
    createBtn.textContent = 'Create step';
    createBtn.style.cssText = 'padding:8px 16px;';
    
    btnGroup.appendChild(cancelBtn);
    btnGroup.appendChild(createBtn);
    form.appendChild(btnGroup);
    
    body.appendChild(form);
    content.appendChild(body);
    overlay.appendChild(content);
    document.body.appendChild(overlay);
    this.overlay = overlay;
    
    // Close on outside click
    overlay.addEventListener('click', (ev) => {
      if (ev.target === overlay) {
        overlay.remove();
      }
    });
    
    // Load documents
    await this._loadDocuments(docSelect);
    
    // Form submission
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      await this._createStep(
        titleInput.value,
        docSelect.value,
        actionSelect.value,
        descTextarea.value
      );
    });
    
    // Update help text when action changes
    actionSelect.addEventListener('change', () => {
      this._updateHelpText(actionSelect.value);
    });
    
    // Focus title
    titleInput.focus();
  }
  
  async _loadDocuments(selectEl) {
    try {
      const res = await fetch('/api/documents/library', { headers: { 'Accept': 'application/json' } });
      if (!res.ok) throw new Error(`Documents library failed: ${res.status}`);
      const data = await res.json();
      const docs = (data && (data.documents || data.docs || [])) || [];
      
      selectEl.innerHTML = '';
      if (!docs.length) {
        selectEl.innerHTML = '<option value="">No documents found</option>';
        return;
      }
      
      docs.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.textContent = `${d.title || d.name || 'Untitled'} (${d.language || 'text'})`;
        selectEl.appendChild(opt);
      });
    } catch (err) {
      console.warn('DocStepBuilder: failed to load documents:', err);
      selectEl.innerHTML = '<option value="">(documents unavailable)</option>';
    }
  }
  
  _updateHelpText(action) {
    const help = document.getElementById('p2-doc-step-help');
    if (!help) return;
    
    const helpTexts = {
      create: 'Create: Creates a new document with the provided content as initial text.',
      update: 'Update: Replaces the entire document content with what you enter here.',
      edit: 'Edit: Use <<<FIND>>>...<<<REPLACE>>>...<<<END>>> blocks to make targeted changes.',
      suggest: 'Suggest: Generates suggestions for the document without modifying it.',
      read: 'Read: Reads the document content (useful for context-aware steps).',
    };
    help.textContent = helpTexts[action] || '';
  }
  
  async _createStep(title, docId, action, description) {
    if (!title || !docId || !action) {
      alert('Please fill in all required fields.');
      return;
    }
    
    const btn = this.overlay.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Creating...';
    
    try {
      const res = await fetch(`/api/plans/${encodeURIComponent(this.planId)}/steps/document`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          doc_id: docId,
          doc_action: action,
          description: description || null,
        }),
      });
      
      const data = await res.json().catch(() => ({}));
      
      if (!res.ok) {
        const msg = data.detail || `Failed (${res.status})`;
        alert(msg);
        throw new Error(msg);
      }
      
      // Close the modal and notify parent
      if (this.overlay) {
        this.overlay.remove();
        this.overlay = null;
      }
      
      // Dispatch a custom event for the parent to handle
      window.dispatchEvent(new CustomEvent('docStepCreated', {
        detail: { step: data },
      }));
    } catch (err) {
      console.error('DocStepBuilder: create step failed:', err);
      alert(`Failed to create step: ${err.message}`);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Create step';
      }
    }
  }
}

// Global helper
let _builder = null;
export function getDocStepBuilder() {
  if (!_builder) {
    _builder = new DocStepBuilder('', '');
  }
  return _builder;
}

export async function openDocStepBuilder(planId, planTitle) {
  const builder = getDocStepBuilder();
  builder.planId = planId;
  builder.planTitle = planTitle;
  await builder.open();
}