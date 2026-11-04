// multiModel/api.js — API client for multi-model conversation threads
/**
 * API client for multi-model conversation threads.
 * Provides methods to create, retrieve, and manage multi-model threads.
 */

const API_BASE = window.location.origin;

/**
 * Create a new multi-model thread with the given models and prompt.
 * @param {string[]} modelIds - List of model IDs to execute concurrently
 * @param {string} prompt - The user prompt to send to all models
 * @param {string[]} [endpointUrls] - Optional list of endpoint URLs
 * @param {string} [sessionId] - Optional parent session ID for UI linking
 * @returns {Promise<{threadId: string, status: string, modelsExecuted: number}>}
 */
export async function createMultiModelThread({ modelIds, prompt, endpointUrls, endpointIds, sessionId }) {
  const formData = new FormData();
  formData.append('prompt', prompt);
  formData.append('model_ids', JSON.stringify(modelIds));
  if (endpointUrls) {
    formData.append('endpoint_urls', JSON.stringify(endpointUrls));
  }
  if (endpointIds) {
    formData.append('endpoint_ids', JSON.stringify(endpointIds));
  }
  if (sessionId) {
    formData.append('session_id', sessionId);
  }
  formData.append('use_web', 'false');
  formData.append('use_research', 'false');

  const response = await fetch(`${API_BASE}/api/chat/multi-model/`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  return await response.json();
}

/**
 * Retrieve all messages from a multi-model thread.
 * @param {string} threadId - The thread ID to retrieve
 * @returns {Promise<{threadId: string, modelIds: string[], messagesByModel: Object<string, any[]>}>}
 */
export async function getMultiModelThread(threadId) {
  const response = await fetch(`${API_BASE}/api/chat/multi-model/${threadId}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Thread not found');
    }
    if (response.status === 401) {
      throw new Error('Authentication required');
    }
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return await response.json();
}

/**
 * List all multi-model threads for the current user.
 * @returns {Promise<Array<{id: string, modelIds: string[], latestMessages: Object, messageCount: number}>>}
 */
export async function listMultiModelThreads() {
  const response = await fetch(`${API_BASE}/api/chat/multi-model/`);

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Authentication required');
    }
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return await response.json();
}

/**
 * Delete a multi-model thread and its associated sessions.
 * @param {string} threadId - The thread ID to delete
 * @returns {Promise<{status: string, threadId: string}>}
 */
export async function deleteMultiModelThread(threadId) {
  const response = await fetch(`${API_BASE}/api/chat/multi-model/${threadId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Thread not found');
    }
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return await response.json();
}
