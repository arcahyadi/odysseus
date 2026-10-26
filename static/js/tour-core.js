// static/js/tour-core.js
// Shared tour primitives — extracted from slashCommands.js so the 12 tour
// slash-commands stop re-declaring identical _makeHalo / _positionTooltip /
// _showStep closures inside every handler. Multi-phase tours (Compare,
// Cookbook, Library, Research, Tasks) still drive the primitives by hand so
// their inter-phase modal-close waits stay explicit; the linear tours call
// `runTour(...)` and get the whole walkthrough in one shot.
//
// Kept in one module so cancelActiveTour can reach into the *current* session
// rather than pattern-match on CSS selectors that any handler might shadow.

const TOOLTIP_ID = 'tour-tooltip';
const STYLE_ID = 'tour-styles';
const MODAL_POLL_TRIES = 25;
const MODAL_POLL_DELAY_MS = 80;
const AFTER_BEFORE_HOOK_DELAY_MS = 160;

// The tour-styles <style> block — hoisted so every tour injects the same
// rules instead of copy-pasting the CSS string nine times. Idempotent:
// if the tag is already there (previous tour in the same session), we skip.
const TOUR_CSS =
  '#tour-tooltip{position:fixed;z-index:10001;background:var(--bg);color:var(--fg);' +
  'border:1px solid var(--border);border-radius:8px;padding:12px 14px;max-width:280px;' +
  'font-family:inherit;font-size:0.8rem;line-height:1.5;' +
  'box-shadow:0 2px 12px rgba(0,0,0,0.3);pointer-events:auto;' +
  'opacity:0;transform:translateY(4px);transition:opacity 0.3s ease-out,transform 0.3s ease-out}' +
  '#tour-tooltip.tour-fade-in{opacity:1;transform:translateY(0)}' +
  '#tour-tooltip .tour-text{margin-bottom:8px;opacity:0.8}' +
  '.tour-nav{display:flex;align-items:center;justify-content:space-between}' +
  '.tour-nav button{background:none;border:1px solid var(--border);color:var(--fg);' +
  'cursor:pointer;font-family:inherit;border-radius:4px;transition:all .1s}' +
  '.tour-nav button:hover{background:color-mix(in srgb,var(--fg) 8%,transparent)}' +
  '.tour-btn-arrow{font-size:1rem;padding:4px 12px;opacity:0.6}' +
  '.tour-btn-arrow:hover{opacity:1}' +
  '.tour-btn-arrow.disabled{opacity:0.15;pointer-events:none}' +
  '.tour-btn-skip{font-size:0.72rem;padding:3px 10px;opacity:0.35;border-color:transparent!important}' +
  '.tour-btn-skip:hover{opacity:0.6}' +
  '.tour-halo{position:fixed;z-index:10000;border:2px solid var(--accent,#7aa2ff);' +
  'border-radius:10px;pointer-events:none;box-shadow:0 0 0 4px rgba(122,162,255,0.18);' +
  'opacity:0;transition:opacity 0.25s ease-out}' +
  '.tour-halo.tour-fade-in{opacity:1}';

export function ensureTourStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const s = document.createElement('style');
  s.id = STYLE_ID;
  s.textContent = TOUR_CSS;
  document.head.appendChild(s);
}

// Clear the chat composer before starting a tour — every tour slash-command
// needs this because the dispatcher doesn't auto-wipe the input, and a
// lingering "/tour-settings" competes with the tooltip visually.
export function clearComposer() {
  const el = document.getElementById('message');
  if (!el) return;
  el.value = '';
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

// A floating halo overlay anchored to a target element. Sits on <body> so
// it isn't clipped by the host modal's overflow. Returns { el, destroy() }.
// `trackAppear: true` also runs a short 500ms rafId loop that keeps
// re-measuring after creation — Settings/Gallery/Notes/Brain use this to
// follow the modal-enter scale animation so the halo doesn't drift.
export function makeHalo(target, { trackAppear = false } = {}) {
  const halo = document.createElement('div');
  halo.className = 'tour-halo';
  document.body.appendChild(halo);
  const update = () => {
    const r = target.getBoundingClientRect();
    halo.style.top    = (r.top - 4) + 'px';
    halo.style.left   = (r.left - 4) + 'px';
    halo.style.width  = (r.width + 8) + 'px';
    halo.style.height = (r.height + 8) + 'px';
  };
  update();
  let _rafId = 0;
  if (trackAppear) {
    const _tStart = performance.now();
    const tick = () => {
      update();
      if (performance.now() - _tStart < 500) _rafId = requestAnimationFrame(tick);
    };
    _rafId = requestAnimationFrame(tick);
  }
  window.addEventListener('resize', update);
  window.addEventListener('scroll', update, true);
  requestAnimationFrame(() => halo.classList.add('tour-fade-in'));
  return {
    el: halo,
    destroy() {
      if (_rafId) cancelAnimationFrame(_rafId);
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
      halo.remove();
    },
  };
}

// Poll until a modal is present (and, when `requireVisible`, not `.hidden`).
// Clicks one of the `openerIds` first so a not-yet-mounted overlay
// (Compare/Research) actually spawns. Returns the element or null.
export async function pollForModal(modalId, { openerIds = [], requireVisible = true, tries = MODAL_POLL_TRIES, delayMs = MODAL_POLL_DELAY_MS } = {}) {
  const check = () => {
    const el = document.getElementById(modalId);
    if (!el) return null;
    if (requireVisible && el.classList.contains('hidden')) return null;
    return el;
  };
  let found = check();
  if (found) return found;
  for (const id of openerIds) {
    const opener = document.getElementById(id);
    if (opener) { opener.click(); break; }
  }
  for (let i = 0; i < tries; i++) {
    await sleep(delayMs);
    found = check();
    if (found) return found;
  }
  return null;
}

export function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// Position the tooltip near `target`. Falls back through below → above →
// right → left, keeping it inside the viewport with a 10px margin.
// `placement: 'center-above'` bypasses target math and pins near the
// top-middle of the viewport — used by opening steps that don't point at
// a specific element.
export function positionTooltip(tooltip, target, placement) {
  tooltip.style.visibility = 'hidden';
  tooltip.style.display = '';
  const tw = tooltip.offsetWidth || 260;
  const th = tooltip.offsetHeight || 100;
  if (placement === 'center-above') {
    tooltip.style.top  = Math.max(10, window.innerHeight * 0.32 - th / 2) + 'px';
    tooltip.style.left = Math.max(10, window.innerWidth / 2 - tw / 2) + 'px';
    tooltip.style.visibility = '';
    return;
  }
  const r = target.getBoundingClientRect();
  const gap = 12;
  let top, left;
  if (r.bottom + gap + th < window.innerHeight - 10) {
    top = r.bottom + gap;
    left = r.left + r.width / 2 - tw / 2;
  } else if (r.top - gap - th > 10) {
    top = r.top - gap - th;
    left = r.left + r.width / 2 - tw / 2;
  } else {
    top = r.top + r.height / 2 - th / 2;
    left = r.right + gap;
    if (left + tw > window.innerWidth - 10) left = r.left - tw - gap;
  }
  if (left + tw > window.innerWidth - 10) left = window.innerWidth - tw - 10;
  if (left < 10) left = 10;
  if (top < 10) top = 10;
  tooltip.style.top = top + 'px';
  tooltip.style.left = left + 'px';
  tooltip.style.visibility = '';
}

// One mutable session shared by beginSession / runSteps / finish. Registry
// entry so cancelActiveTour from anywhere can tear down the current run
// without pattern-matching on class names that a handler may shadow.
let _current = null;

export function beginSession({ reply, modalId, openerIds = [], bailMessage, requireVisible = true, haloTracksAppear = false } = {}) {
  ensureTourStyles();
  clearComposer();
  const ctx = { reply, halos: [], tooltip: null, modal: null, ended: false };

  ctx.ensureModal = async () => {
    if (modalId) {
      const m = await pollForModal(modalId, { openerIds, requireVisible });
      if (!m) {
        if (typeof reply === 'function') reply(bailMessage || `Could not open ${modalId}.`);
        ctx.ended = true;
        return null;
      }
      ctx.modal = m;
    }
    document.body.classList.add('tour-active');
    const tooltip = document.getElementById(TOOLTIP_ID) || document.createElement('div');
    tooltip.id = TOOLTIP_ID;
    if (!tooltip.parentNode) document.body.appendChild(tooltip);
    ctx.tooltip = tooltip;
    _current = ctx;
    return ctx;
  };

  ctx.addHalo = (target) => {
    const h = makeHalo(target, { trackAppear: haloTracksAppear });
    ctx.halos.push(h);
    return h;
  };

  ctx.clearHalos = () => {
    ctx.halos.forEach(h => h.destroy());
    ctx.halos = [];
    document.querySelectorAll('.tour-halo').forEach(e => e.remove());
  };

  ctx.clear = () => {
    ctx.clearHalos();
    if (ctx.tooltip) ctx.tooltip.remove();
    document.querySelectorAll('.odysseus-highlight').forEach(
      e => e.classList.remove('odysseus-highlight')
    );
    document.body.classList.remove('tour-active');
    if (_current === ctx) _current = null;
    ctx.ended = true;
  };

  ctx.showStep = (step, { isFirst, isLast } = {}) => new Promise(resolve => {
    ctx.clearHalos();
    if (step.before) { try { step.before(ctx.modal); } catch (_) {} }
    setTimeout(() => {
      const target = document.querySelector(step.sel);
      if (!target) return resolve('skip');
      ctx.addHalo(target);
      const extra = step.extraSel ? document.querySelector(step.extraSel) : null;
      if (extra) ctx.addHalo(extra);
      target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      ctx.tooltip.classList.remove('tour-fade-in');
      const hint = step.advanceOnClick
        ? '<div style="font-size:0.72rem;opacity:0.45;margin-bottom:6px;">Click the highlighted element to continue.</div>'
        : '';
      ctx.tooltip.innerHTML =
        '<div class="tour-text">' + step.text + '</div>' + hint +
        '<div class="tour-nav">' +
          '<button class="tour-btn-arrow' + (isFirst ? ' disabled' : '') + '" data-act="back">←</button>' +
          '<button class="tour-btn-skip" data-act="skip">' + (isLast ? 'done' : 'skip tour') + '</button>' +
          '<button class="tour-btn-arrow" data-act="next">' + (isLast ? '✓' : '→') + '</button>' +
        '</div>';
      requestAnimationFrame(() => {
        positionTooltip(ctx.tooltip, target, step.placement);
        ctx.tooltip.classList.add('tour-fade-in');
      });

      let resolved = false;
      let onTarget = null;
      const cleanup = () => {
        ctx.tooltip.removeEventListener('click', onClick);
        if (onTarget) {
          target.removeEventListener('click', onTarget, true);
          if (extra) extra.removeEventListener('click', onTarget, true);
          document.removeEventListener('click', onTarget, true);
        }
      };
      const onClick = (e) => {
        if (resolved) return;
        const hit = e.target.closest && e.target.closest('[data-act]');
        const act = hit && hit.dataset.act;
        if (!act) return;
        resolved = true;
        cleanup();
        resolve(act);
      };
      ctx.tooltip.addEventListener('click', onClick);
      if (step.interactive || step.advanceOnClick) {
        onTarget = (e) => {
          if (resolved) return;
          if (step.advanceOnClick) {
            if (!target.contains(e.target) && e.target !== target) return;
          }
          resolved = true;
          cleanup();
          resolve('next');
        };
        target.addEventListener('click', onTarget, true);
        if (extra) extra.addEventListener('click', onTarget, true);
      }
    }, step.before ? AFTER_BEFORE_HOOK_DELAY_MS : 0);
  });

  // Linear run of a steps array. Returns 'skip' if the user bailed out
  // via the skip button or a missing target, else 'done'. Handles the
  // back-arrow rewind by decrementing the outer index.
  ctx.runSteps = async (steps) => {
    for (let i = 0; i < steps.length; i++) {
      const res = await ctx.showStep(steps[i], {
        isFirst: i === 0,
        isLast: i === steps.length - 1,
      });
      if (res === 'skip') return 'skip';
      if (res === 'back' && i > 0) { i -= 2; }
    }
    return 'done';
  };

  return ctx;
}

// Convenience wrapper: modal open → linear steps → cleanup → typewriterReply.
// The 5 "simple" tours (Theme/Settings/Gallery/Notes/Brain) go through here.
// Anything with a mid-tour modal-close interlude uses `beginSession` and
// drives the primitives directly.
//
// `onBefore(session)` runs right after the modal is up and before the first
// step — for one-off preflight side effects (e.g. hiding a first-open hint).
// `onFinish(session)` runs after the last step and before `_clear()` — for
// tours that want to land on a friendly starting tab.
export async function runTour({ modalId, openerIds, bailMessage, requireVisible = true, haloTracksAppear = false, steps, doneText, reply, done, onBefore, onFinish }) {
  const session = beginSession({ reply, modalId, openerIds, bailMessage, requireVisible, haloTracksAppear });
  const ok = await session.ensureModal();
  if (!ok) return true;
  if (onBefore) { try { await onBefore(session); } catch (_) {} }
  const res = await session.runSteps(steps);
  if (res !== 'skip' && onFinish) { try { await onFinish(session); } catch (_) {} }
  session.clear();
  if (res !== 'skip' && typeof done === 'function' && doneText) {
    await done(doneText);
  }
  return true;
}

// Global cancel — replaces the previous window.cancelActiveTour that had to
// pattern-match on selector classes. Still exposes a window hook so
// tourAutoplay.js and any modal-close handler can invoke it.
export function cancelActiveTour(_reason) {
  if (_current) { try { _current.clear(); } catch (_) {} _current = null; }
  document.querySelectorAll('.odysseus-highlight, .odysseus-highlight-click')
    .forEach(e => e.classList.remove('odysseus-highlight', 'odysseus-highlight-click'));
  document.querySelectorAll('.tour-halo').forEach(e => e.remove());
  document.getElementById(TOOLTIP_ID)?.remove();
  document.body?.classList.remove('tour-active');
}

if (typeof window !== 'undefined') {
  window.cancelActiveTour = cancelActiveTour;
}

export default {
  ensureTourStyles,
  clearComposer,
  makeHalo,
  pollForModal,
  positionTooltip,
  beginSession,
  runTour,
  cancelActiveTour,
  sleep,
};
