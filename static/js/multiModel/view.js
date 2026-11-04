// multiModel/view.js — Multi-model thread view controller
/**
 * Main controller for multi-model thread view.
 * Handles API calls, UI rendering, and scroll synchronization.
 */

import { createMultiModelThread, getMultiModelThread, listMultiModelThreads, deleteMultiModelThread } from './api.js';
import { createScrollSyncManager } from './scrollSync.js';
import { renderMultiModelContainer, updatePaneStatus, addMessageToPane, renderFailedModel, syncPanesToMessageIndex } from './renderer.js';
import uiModule from '../ui.js?v=20260916largetoolscroll1';

const escapeHtml = uiModule.esc;

/**
 * Multi-model thread view controller.
 */
class MultiModelView {
  constructor(apiBase) {
    this.apiBase = apiBase;
    this.activeThread = null;
    this.scrollSyncManager = null;
    this.modelIds = [];
    this.messagesByModel = {};
    this.isInitialized = false;
  }

  /**
   * Load and render a multi-model thread.
   * @param {string} threadId - The thread ID to load
   * @returns {Promise<void>}
   */
  async loadThread(threadId, opts = {}) {
    try {
      this.activeThread = await getMultiModelThread(threadId);
      this.modelIds = this.activeThread.model_ids;
      this.messagesByModel = this.activeThread.messages_by_model;

      // Render the thread UI
      const container = renderMultiModelContainer(
        threadId,
        this.modelIds,
        this.messagesByModel
      );

      // Insert into DOM
      const mainContent = document.querySelector('.main-content');
      if (mainContent) {
        mainContent.innerHTML = '';
        mainContent.appendChild(container);
      }

      // Initialize scroll sync
      this.scrollSyncManager = createScrollSyncManager(container);
      this.scrollSyncManager.panes.forEach(pane => {
        pane.addEventListener('scroll', () => this.scrollSyncManager.syncScroll());
      });

      // Add tab switching functionality
      this._setupTabSwitching(container);

      // Add close button functionality
      this._setupCloseButton(container, opts.onClose);

      this.isInitialized = true;
    } catch (error) {
      console.error('Failed to load multi-model thread:', error);
      this._renderError(error.message);
    }
  }

  /**
   * Create a new multi-model thread.
   * @param {string[]} modelIds - List of model IDs to execute
   * @param {string} prompt - User prompt
   * @param {string[]} [endpointUrls] - Parallel endpoint URLs (required when the
   *   same model id is served by more than one endpoint)
   * @returns {Promise<{threadId: string, status: string}>}
   */
  async createThread(modelIds, prompt, endpointUrls, endpointIds) {
    try {
      const result = await createMultiModelThread({
        modelIds,
        prompt,
        endpointUrls,
        endpointIds,
      });
      return result;
    } catch (error) {
      console.error('Failed to create multi-model thread:', error);
      throw error;
    }
  }

  /**
   * List all multi-model threads.
   * @returns {Promise<Array>} - List of threads
   */
  async listThreads() {
    try {
      return await listMultiModelThreads();
    } catch (error) {
      console.error('Failed to list multi-model threads:', error);
      throw error;
    }
  }

  /**
   * Delete a multi-model thread.
   * @param {string} threadId - The thread ID to delete
   * @returns {Promise<void>}
   */
  async deleteThread(threadId) {
    try {
      await deleteMultiModelThread(threadId);
      this.activeThread = null;
      this.isInitialized = false;
    } catch (error) {
      console.error('Failed to delete multi-model thread:', error);
      throw error;
    }
  }

  /**
   * Render error message.
   * @param {string} message - Error message
   */
  _renderError(message) {
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
      mainContent.innerHTML = `
        <div class="error-message">
          <h2>Error</h2>
          <p>${escapeHtml(message)}</p>
          <button onclick="window.location.reload()">Reload</button>
        </div>
      `;
    }
  }

  /**
   * Setup tab switching between models.
   * @param {HTMLElement} container - Main container
   */
  _setupTabSwitching(container) {
    const tabs = container.querySelectorAll('.multi-model-tab');
    const panes = container.querySelectorAll('.multi-model-pane');

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        // Update active tab
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // Update active pane
        const modelIndex = parseInt(tab.dataset.modelIndex, 10);
        panes.forEach((pane, idx) => {
          pane.classList.remove('active');
          if (idx === modelIndex) {
            pane.classList.add('active');
          }
        });

        // Sync scroll to active pane
        this.scrollSyncManager.syncScroll();
      });
    });
  }

  /**
   * Setup close button functionality.
   * @param {HTMLElement} container - Main container
   * @param {Function} [onClose] - Called instead of reloading the shell
   */
  _setupCloseButton(container, onClose) {
    const closeBtn = container.querySelector('.multi-model-close-btn');
    if (!closeBtn) return;
    closeBtn.addEventListener('click', () => {
      // Closing is non-destructive: the thread stays in history. Return to the
      // caller's view, or fall back to reloading the app shell.
      if (typeof onClose === 'function') onClose();
      else window.location.href = window.location.pathname;
    });
  }

  /**
   * Update pane status.
   * @param {number} modelIndex - Model index
   * @param {'pending'|'streaming'|'completed'|'failed'} status - Status
   * @param {string} message - Optional status message
   */
  updatePaneStatus(modelIndex, status, message = '') {
    const panes = this.scrollSyncManager?.panes || [];
    if (panes[modelIndex]) {
      updatePaneStatus(panes[modelIndex], status, message);
    }
  }

  /**
   * Add a new message to a pane.
   * @param {number} modelIndex - Model index
   * @param {Object} message - Message object
   */
  addMessageToPane(modelIndex, message) {
    const panes = this.scrollSyncManager?.panes || [];
    if (panes[modelIndex]) {
      addMessageToPane(panes[modelIndex], message);
      this.scrollSyncManager.syncScroll();
    }
  }

  /**
   * Sync panes to show same message index.
   * @param {number} messageIndex - Message index to sync to
   */
  syncToMessageIndex(messageIndex) {
    const panes = this.scrollSyncManager?.panes || [];
    syncPanesToMessageIndex(panes, messageIndex);
  }
}

// Export singleton instance
export const multiModelView = new MultiModelView();
