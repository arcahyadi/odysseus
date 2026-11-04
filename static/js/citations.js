/**
 * citations.js — Citation chips/box for RAG and research answers.
 * Requirements: 9.1 (phase 2)
 *
 * Structured citations are saved on assistant-message metadata under
 * `citations` (array of {chunk_id?, source_url?, source_title?, snippet?,
 * confidence_score?}). This module renders them as a collapsible box under
 * the answer, both for persisted history (chatRenderer restore path) and for
 * live SSE bubbles (chat.js finish path).
 */
import uiModule from './ui.js?v=20260916largetoolscroll1';

/**
 * Build the HTML string for a collapsible citations box. Items carry a
 * numbered source link, a short snippet, and a confidence percentage when
 * the backend supplied one.
 * @param {Array<{source_url, source_title, snippet, confidence_score}>} citations
 * @returns {string} HTML ('' when no citations)
 */
export function buildCitationsBox(citations) {
  if (!citations || !citations.length) return '';
  const esc = uiModule.esc;
  const items = [];
  for (let i = 0; i < citations.length; i++) {
    const c = citations[i] || {};
    const url = c.source_url || c.url || '';
    const title = c.source_title || c.title || url || `Source ${i + 1}`;
    const pct = (typeof c.confidence_score === 'number')
      ? `<span class="citation-confidence">${(c.confidence_score * 100).toFixed(0)}%</span>` : '';
    let linkHtml = `<span class="citation-title">${esc(title)}</span>`;
    if (/^https?:\/\//i.test(url)) {
      linkHtml = `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" class="citation-link" title="${esc(url)}">${linkHtml}</a>`;
    }
    items.push(
      '<div class="citation-item">'
      + `<span class="citation-num">${i + 1}</span>`
      + linkHtml
      + pct
      + (c.snippet ? `<div class="citation-snippet">${esc(String(c.snippet).slice(0, 300))}</div>` : '')
      + '</div>'
    );
  }
  return `<details class="citations-box"><summary>Citations (${citations.length})</summary>${items.join('')}</details>`;
}

/**
 * CitationRenderer — small class mirroring the phase-1 attach pattern.
 * Attaches to a rendered assistant message element and/or restores from
 * metadata during history render.
 */
export class CitationRenderer {
  /**
   * @param {HTMLElement} messageEl
   * @param {Array} citations
   */
  static renderInto(messageEl, citations) {
    if (!messageEl || !citations || !citations.length) return;
    if (messageEl.querySelector('.citations-box')) return;
    const host = messageEl.querySelector('.body') || messageEl;
    host.insertAdjacentHTML('beforeend', buildCitationsBox(citations));
  }

  /**
   * Metadata-restore hook for history rendering.
   * @param {HTMLElement} messageEl
   * @param {object} metadata - assistant message metadata dict
   */
  static restoreFromMetadata(messageEl, metadata) {
    if (messageEl && metadata && Array.isArray(metadata.citations) && metadata.citations.length) {
      CitationRenderer.renderInto(messageEl, metadata.citations);
    }
  }
}

export default CitationRenderer;
