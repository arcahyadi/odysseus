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

    this.containerEl.appendChild(wrap);
  }
}
