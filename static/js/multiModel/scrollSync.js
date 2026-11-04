// multiModel/scrollSync.js — synchronized scrolling across model panes
/**
 * Manages synchronized scrolling across multiple model panes.
 * When one pane scrolls, others scroll to the same relative position.
 */

/**
 * Scroll synchronization state
 * @typedef {Object} ScrollSyncState
 * @property {HTMLElement} container - Main scroll container
 * @property {HTMLElement[]} panes - Array of pane elements to sync
 * @property {Map<number, number>} scrollPositions - Track scroll positions per pane
 * @property {boolean} isSyncing - Prevent recursive scroll events
 */

/**
 * Initialize scroll synchronization for multi-model panes.
 * @param {HTMLElement} container - Main container with all panes
 * @param {string} paneSelector - CSS selector for pane elements (e.g., '.multi-model-pane')
 * @returns {Object} - API for managing scroll sync
 */
export function createScrollSyncManager(container, paneSelector = '.multi-model-pane') {
  const panes = Array.from(container.querySelectorAll(paneSelector));
  const scrollPositions = new Map();
  let isSyncing = false;

  /**
   * Sync all panes to the same scroll position.
   * @param {number} targetScrollTop - Scroll position to sync to
   * @param {HTMLElement} sourcePane - Optional source pane to exclude from sync
   */
  function syncScrollTo(targetScrollTop, sourcePane = null) {
    if (isSyncing) return;
    isSyncing = true;

    panes.forEach(pane => {
      if (pane !== sourcePane) {
        pane.scrollTop = targetScrollTop;
      }
    });

    isSyncing = false;
  }

  /**
   * Calculate and set scroll position for all panes.
   * Uses percentage-based positioning for alignment.
   */
  function syncScroll() {
    if (isSyncing) return;

    // Use the first pane as the source
    const sourcePane = panes[0];
    if (!sourcePane) return;

    const scrollTop = sourcePane.scrollTop;
    const scrollHeight = sourcePane.scrollHeight;
    const clientHeight = sourcePane.clientHeight;

    // Calculate scroll percentage (0-1)
    const scrollPercent = scrollHeight > clientHeight 
      ? scrollTop / (scrollHeight - clientHeight)
      : 0;

    isSyncing = true;

    panes.forEach(pane => {
      if (pane !== sourcePane) {
        const paneScrollHeight = pane.scrollHeight;
        const paneClientHeight = pane.clientHeight;
        
        if (paneScrollHeight > paneClientHeight) {
          const targetScrollTop = scrollPercent * (paneScrollHeight - paneClientHeight);
          if (Math.abs(pane.scrollTop - targetScrollTop) > 1) {
            pane.scrollTop = targetScrollTop;
          }
        }
      }
    });

    isSyncing = false;
  }

  /**
   * Handle scroll event on a pane.
   * @param {Event} event - Scroll event
   */
  function handlePaneScroll(event) {
    if (isSyncing) return;
    syncScroll();
  }

  /**
   * Add scroll listener to a pane.
   * @param {HTMLElement} pane - Pane element to listen to
   */
  function attachScrollListener(pane) {
    if (!panes.includes(pane)) {
      panes.push(pane);
    }
    pane.addEventListener('scroll', handlePaneScroll);
  }

  /**
   * Remove scroll listener from a pane.
   * @param {HTMLElement} pane - Pane element to remove
   */
  function detachScrollListener(pane) {
    const index = panes.indexOf(pane);
    if (index > -1) {
      panes.splice(index, 1);
      pane.removeEventListener('scroll', handlePaneScroll);
    }
  }

  /**
   * Scroll to a specific message index across all panes.
   * @param {number} messageIndex - Message index to scroll to
   */
  function scrollToMessageIndex(messageIndex) {
    panes.forEach(pane => {
      const messageEl = pane.querySelector(`[data-message-index="${messageIndex}"]`);
      if (messageEl) {
        messageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  }

  /**
   * Reset scroll synchronization state.
   */
  function reset() {
    scrollPositions.clear();
    isSyncing = false;
  }

  return {
    panes,
    scrollPositions,
    syncScroll,
    attachScrollListener,
    detachScrollListener,
    scrollToMessageIndex,
    reset,
    get isSyncing() { return isSyncing; }
  };
}

/**
 * Initialize scroll sync for all multi-model panes on the page.
 */
export function initializeScrollSync() {
  const container = document.querySelector('.multi-model-container');
  if (container) {
    return createScrollSyncManager(container);
  }
  return null;
}