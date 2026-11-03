/**
 * plan-tracker.js — Plan progress widget.
 * Requirements: 6.8
 */

export class PlanTracker {
  /**
   * @param {string} planId
   * @param {HTMLElement} containerEl
   */
  constructor(planId, containerEl) {
    this.planId = planId;
    this.containerEl = containerEl;
    this._intervalId = null;
  }

  /** Fetch latest plan state and re-render. */
  async refresh() {
    try {
      const res = await fetch(`/api/plans/${encodeURIComponent(this.planId)}`);
      if (!res.ok) return;
      const plan = await res.json();
      this._render(plan);
    } catch (err) {
      console.warn('PlanTracker refresh failed:', err);
    }
  }

  /** Start auto-refreshing every `intervalMs` milliseconds. */
  startPolling(intervalMs = 3000) {
    this.stopPolling();
    this.refresh();
    this._intervalId = setInterval(() => this.refresh(), intervalMs);
  }

  /** Stop auto-refreshing. */
  stopPolling() {
    if (this._intervalId !== null) {
      clearInterval(this._intervalId);
      this._intervalId = null;
    }
  }

  // ── Private ──────────────────────────────────────────────────────────────

  _render(plan) {
    const steps = Array.isArray(plan.steps) ? plan.steps : [];
    const total = steps.length || plan.step_count || 0;
    const done = steps.filter(s => s.status === 'done' || s.status === 'skipped').length
      || plan.done_count || 0;
    const running = steps.find(s => s.status === 'running');

    this.containerEl.innerHTML = '';

    const wrap = document.createElement('div');
    wrap.className = 'plan-progress';

    const title = document.createElement('span');
    title.className = 'plan-progress__title';
    title.textContent = plan.title || 'Plan';

    const prog = document.createElement('progress');
    prog.value = done;
    prog.max = total || 1;
    prog.setAttribute('aria-label', `${done} of ${total} steps complete`);

    const counts = document.createElement('span');
    counts.className = 'plan-progress__counts';
    counts.textContent = `${done} / ${total} steps`;

    wrap.appendChild(title);
    wrap.appendChild(prog);
    wrap.appendChild(counts);

    if (running) {
      const curr = document.createElement('span');
      curr.className = 'plan-progress__current';
      curr.textContent = `▶ ${running.title}`;
      wrap.appendChild(curr);
    }

    const statusBadge = document.createElement('span');
    statusBadge.className = `plan-progress__status plan-progress__status--${plan.status}`;
    statusBadge.textContent = plan.status || '';
    wrap.appendChild(statusBadge);

    // Render document-aware steps
    const docSteps = steps.filter(s => s.doc_id && s.doc_action);
    if (docSteps.length > 0) {
      const docSection = document.createElement('div');
      docSection.className = 'plan-progress__doc-steps';
      docSection.style.cssText = 'margin-top:8px;padding-top:8px;border-top:1px solid var(--border);';
      
      const docTitle = document.createElement('span');
      docTitle.className = 'plan-progress__doc-title';
      docTitle.textContent = `${docSteps.length} document step(s):`;
      docTitle.style.cssText = 'font-size:0.85em;font-weight:600;color:color-mix(in srgb, var(--fg) 70%, transparent);';
      docSection.appendChild(docTitle);
      
      docSteps.forEach(s => {
        const stepBadge = document.createElement('span');
        stepBadge.className = 'plan-progress__doc-step';
        stepBadge.style.cssText = 'display:inline-block;margin-right:8px;padding:2px 6px;background:color-mix(in srgb, var(--accent) 15%, transparent);border-radius:3px;font-size:0.8em;';
        
        const actionBadge = document.createElement('span');
        actionBadge.style.cssText = 'margin-right:4px;font-weight:600;';
        actionBadge.textContent = s.doc_action?.toUpperCase() || '';
        
        const actionLabel = document.createElement('span');
        const actionLabels = {
          'create': 'create',
          'update': 'update',
          'edit': 'edit',
          'suggest': 'suggest',
          'read': 'read',
        };
        actionLabel.textContent = actionLabels[s.doc_action] || s.doc_action || '';
        
        stepBadge.appendChild(actionBadge);
        stepBadge.appendChild(actionLabel);
        docSection.appendChild(stepBadge);
      });
      
      wrap.appendChild(docSection);
    }

    this.containerEl.appendChild(wrap);
  }
}
