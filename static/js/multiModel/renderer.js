// multiModel/renderer.js — Render multi-model thread UI
/**
 * Renders multi-model thread UI with synchronized panes.
 */

import uiModule from '../ui.js';

const escapeHtml = uiModule.esc;

/**
 * Render the multi-model thread layout container.
 * @param {string} threadId - The thread ID
 * @param {string[]} modelIds - List of model IDs
 * @param {Object<string, any[]>} messagesByModel - Messages grouped by model
 * @returns {HTMLElement} - The container element
 */
export function renderMultiModelContainer(threadId, modelIds, messagesByModel) {
  const container = document.createElement('div');
  container.className = 'multi-model-container';
  container.dataset.threadId = threadId;

  // Render header
  const header = document.createElement('header');
  header.className = 'multi-model-header';
  header.innerHTML = `
    <h2>Multi-model Conversation</h2>
    <div class="multi-model-controls">
      <button class="multi-model-close-btn" title="Close multi-model view">
        <svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 3l10 10M13 3L3 13" stroke="currentColor" stroke-width="2"/></svg>
      </button>
    </div>
  `;
  container.appendChild(header);

  // Render model tabs
  const tabsContainer = document.createElement('div');
  tabsContainer.className = 'multi-model-tabs';
  
  modelIds.forEach((modelId, index) => {
    const tab = document.createElement('button');
    tab.className = `multi-model-tab ${index === 0 ? 'active' : ''}`;
    tab.dataset.modelIndex = index;
    tab.dataset.modelId = modelId;
    tab.innerHTML = `
      <span class="model-name">${escapeHtml(getModelDisplayName(modelId))}</span>
      <span class="model-status"></span>
    `;
    tabsContainer.appendChild(tab);
  });
  
  container.appendChild(tabsContainer);

  // Render panes container
  const panesContainer = document.createElement('div');
  panesContainer.className = 'multi-model-panes';

  modelIds.forEach((modelId, index) => {
    const messages = messagesByModel[modelId] || [];
    const pane = document.createElement('div');
    pane.className = `multi-model-pane ${index === 0 ? 'active' : ''}`;
    pane.dataset.modelIndex = index;
    pane.dataset.modelId = modelId;
    pane.innerHTML = `
      <div class="multi-model-pane-header">
        <h3>${escapeHtml(getModelDisplayName(modelId))}</h3>
        <span class="pane-status"></span>
      </div>
      <div class="multi-model-history" id="multi-model-history-${index}">
        ${messages.length > 0 ? renderMessages(messages) : '<p class="pane-placeholder">Waiting for responses...</p>'}
      </div>
    `;
    panesContainer.appendChild(pane);
  });

  container.appendChild(panesContainer);

  return container;
}

/**
 * Render messages in a pane.
 * @param {any[]} messages - Array of messages
 * @returns {string} - HTML string for messages
 */
function renderMessages(messages) {
  return messages.map((msg, idx) => {
    const role = msg.role || 'assistant';
    const content = msg.content || '';
    const isError = content.startsWith('[Error:');

    return `
      <div class="msg ${role === 'user' ? 'msg-user' : 'msg-ai'}" data-message-index="${idx}">
        <div class="role">${role === 'user' ? 'You' : (isError ? 'Error' : 'AI')}</div>
        <div class="body ${isError ? 'error-message' : ''}">
          ${isError ? `<span class="error-icon">⚠️</span>` : ''}
          <div class="content">${escapeHtml(content)}</div>
        </div>
        ${msg.timestamp ? `<span class="msg-time">${escapeHtml(new Date(msg.timestamp).toLocaleTimeString())}</span>` : ''}
      </div>
    `;
  }).join('');
}

/**
 * Get display name for a model ID.
 * @param {string} modelId - The model ID
 * @returns {string} - Display name
 */
function getModelDisplayName(modelId) {
  // Extract model name from ID for display
  const parts = modelId.split('/');
  return parts[parts.length - 1] || modelId;
}

/**
 * Update pane status.
 * @param {HTMLElement} pane - Pane element
 * @param {'pending'|'streaming'|'completed'|'failed'} status - Status
 * @param {string} message - Optional status message
 */
export function updatePaneStatus(pane, status, message = '') {
  const statusEl = pane.querySelector('.pane-status');
  if (statusEl) {
    statusEl.className = `pane-status pane-status-${status}`;
    statusEl.textContent = message;
  }
}

/**
 * Add a new message to a pane.
 * @param {HTMLElement} pane - Pane element
 * @param {Object} message - Message object
 */
export function addMessageToPane(pane, message) {
  const historyEl = pane.querySelector('.multi-model-history');
  if (!historyEl) return;

  const messages = pane.querySelectorAll('.msg');
  const messageIndex = messages.length;

  const msgEl = document.createElement('div');
  msgEl.className = `msg ${message.role === 'user' ? 'msg-user' : 'msg-ai'}`;
  msgEl.dataset.messageIndex = messageIndex;
  msgEl.innerHTML = `
    <div class="role">${message.role === 'user' ? 'You' : 'AI'}</div>
    <div class="body">
      <div class="content">${escapeHtml(message.content)}</div>
    </div>
  `;
  historyEl.appendChild(msgEl);
}

/**
 * Render placeholder for failed model.
 * @param {HTMLElement} pane - Pane element
 * @param {string} errorMessage - Error message
 */
export function renderFailedModel(pane, errorMessage) {
  const historyEl = pane.querySelector('.multi-model-history');
  if (!historyEl) return;

  historyEl.innerHTML = `
    <div class="msg msg-ai pane-error">
      <div class="role">Error</div>
      <div class="body error-message">
        <span class="error-icon">⚠️</span>
        <div class="content">${escapeHtml(errorMessage)}</div>
      </div>
    </div>
  `;
}

/**
 * Sync panes to show same message index.
 * @param {HTMLElement[]} panes - Array of pane elements
 * @param {number} messageIndex - Message index to sync to
 */
export function syncPanesToMessageIndex(panes, messageIndex) {
  panes.forEach(pane => {
    const messageEl = pane.querySelector(`[data-message-index="${messageIndex}"]`);
    if (messageEl) {
      // Calculate scroll position to center the message
      const paneRect = pane.getBoundingClientRect();
      const msgRect = messageEl.getBoundingClientRect();
      const offset = msgRect.top - paneRect.top - paneRect.height / 2 + msgRect.height / 2;
      pane.scrollTop += offset;
    }
  });
}