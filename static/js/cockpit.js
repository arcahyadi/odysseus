// static/js/cockpit.js
// Persistent "run cockpit": continuous runtime state as chips.
// Inputs: run_status SSE payloads (via window.cockpit.update) + /api/health poll
//         + ThoughtBus phase_enter/phase_exit events.
// Output: contents of #run-cockpit. No dependency on chat internals.
(function () {
  'use strict';
  var MUTED = '\u2014'; // em dash "\u2014"
  var PHASES = ['CLASSIFY', 'KNOW', 'PLAN', 'BUILD', 'QUALITY', 'AUTOEVAL', 'MEMORY_OBSERVE'];
  var _activePhase = null;
  var _phaseIndex = -1;
  var _phaseTotal = 7;

  function esc(s) { return String(s == null ? '' : s).replace(/[<>&]/g, ''); }

  function driftClass(level) {
    if (level === 'high') return 'chip-bad';
    if (level === 'med') return 'chip-warn';
    if (level === 'low') return 'chip-ok';
    return 'chip-muted';
  }

  function setChip(id, label, value, cls) {
    var el = document.getElementById(id);
    if (!el) return;
    el.className = 'cockpit-chip ' + (cls || 'chip-muted');
    el.innerHTML = '<span class="chip-label">' + esc(label) + '</span>' +
      '<span class="chip-val">' + esc(value == null ? MUTED : value) + '</span>';
  }

  // ── ThoughtBus phase bar ──
  function renderPhaseBar() {
    var el = document.getElementById('cockpit-phase-bar');
    if (!el) return;
    var html = '';
    for (var i = 0; i < PHASES.length; i++) {
      var cls = 'pb-dot';
      if (i < _phaseIndex) cls += ' pb-done';
      else if (i === _phaseIndex) cls += ' pb-active';
      html += '<span class="' + cls + '" title="' + PHASES[i] + '">' +
        PHASES[i].charAt(0) + '</span>';
      if (i < PHASES.length - 1) html += '<span class="pb-line"></span>';
    }
    el.innerHTML = html;
  }

  var cockpit = {
    update: function (s) {
      if (!s) return;
      // Honesty: the phase value is the hardcoded default (BUILD/PLAN) unless an
      // orchestrator is actually active (phase_active). Show the value, but only
      // colour it "healthy" when it reflects real orchestration — otherwise neutral.
      setChip('cockpit-phase', 'phase', s.phase || _activePhase || null,
        (s.phase && s.phase_active) ? 'chip-ok' : (_activePhase ? 'chip-ok' : 'chip-muted'));
      setChip('cockpit-drift', 'drift', s.drift || null, driftClass(s.drift));
      if (s.iters && typeof s.iters.used === 'number') {
        setChip('cockpit-iters', 'iters', s.iters.used + '/' + s.iters.max, 'chip-ok');
      }
      if (s.budget && s.budget.pct != null) {
        var cls = s.budget.pct >= 85 ? 'chip-bad' : (s.budget.pct >= 60 ? 'chip-warn' : 'chip-ok');
        setChip('cockpit-budget', 'budget', s.budget.pct + '%', cls);
      } else {
        setChip('cockpit-budget', 'budget', null, 'chip-muted');
      }
    },

    // ── ThoughtBus integration ──
    onThoughtBusEvent: function (evt) {
      if (!evt) return;
      if (evt.type === 'phase_enter' && evt.phase) {
        _activePhase = evt.phase;
        _phaseIndex = PHASES.indexOf(evt.phase);
        _phaseTotal = evt.total || 7;
        setChip('cockpit-phase', 'phase', evt.phase + ' (' + ((evt.index||0)) + '/' + _phaseTotal + ')', 'chip-ok');
        renderPhaseBar();
      } else if (evt.type === 'phase_exit' && evt.phase) {
        setChip('cockpit-phase', 'phase', evt.phase + ' \u2713', 'chip-muted');
      } else if (evt.type === 'thought_bus') {
        if (evt.status === 'complete') {
          _activePhase = null;
          _phaseIndex = PHASES.length;
          setChip('cockpit-phase', 'phase', 'done', 'chip-ok');
          renderPhaseBar();
          // Budget update
          if (evt.budget && evt.budget.percent != null) {
            var pct = evt.budget.percent;
            var cls = pct >= 85 ? 'chip-bad' : (pct >= 60 ? 'chip-warn' : 'chip-ok');
            setChip('cockpit-budget', 'budget', pct + '%', cls);
          }
        } else if (evt.status === 'disabled') {
          _activePhase = null;
          setChip('cockpit-phase', 'phase', 'direct', 'chip-muted');
        }
      }
      // Agent dispatch
      if (evt.type === 'agent_dispatch' && evt.agents) {
        setChip('cockpit-iters', 'agents', evt.agents.length + ' active', 'chip-ok');
      }
      // Model selected
      if (evt.type === 'model_selected' && evt.model) {
        var shortModel = evt.model.split('/').pop() || evt.model;
        setChip('cockpit-drift', 'model', shortModel, 'chip-ok');
      }
    },

    pollHealth: function () {
      fetch('/api/health', { credentials: 'same-origin' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          var ok = j && (j.status === 'ok' || j.status === 'healthy' || j.ok === true);
          setChip('cockpit-health', 'health', ok ? 'ok' : 'down', ok ? 'chip-ok' : 'chip-bad');
        })
        .catch(function () { setChip('cockpit-health', 'health', '?', 'chip-muted'); });
    },
  };

  window.cockpit = cockpit;
  document.addEventListener('DOMContentLoaded', function () {
    cockpit.pollHealth();
    setInterval(cockpit.pollHealth, 15000);
  });
})();
