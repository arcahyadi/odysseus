// multiModel/index.js — Multi-model conversation threads entry point
/**
 * Entry point for multi-model conversation threads feature.
 * Exports all submodules for use in the main application.
 */

export { createMultiModelThread, getMultiModelThread, listMultiModelThreads, deleteMultiModelThread } from './api.js';
export { createScrollSyncManager, initializeScrollSync } from './scrollSync.js';
export { renderMultiModelContainer, updatePaneStatus, addMessageToPane, renderFailedModel, syncPanesToMessageIndex } from './renderer.js';
export { multiModelView } from './view.js';