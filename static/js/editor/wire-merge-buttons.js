/**
 * Layer merge / flatten buttons in the layer-panel footer:
 *
 *   #ge-flatten     Flatten Copy — merge every visible layer into a
 *                   new "Flattened" layer, keep originals.
 *   #ge-merge-all   Merge All — flatten every VISIBLE layer into the
 *                   lowest visible one. Hidden layers dropped. Base
 *                   = lowest visible (not bottom of stack) so a
 *                   hidden base can't absorb the visible stack into
 *                   an invisible result.
 *   #ge-merge-down  Merge active layer into the one beneath it.
 *
 * @param {{
 *   saveState:        (label?: string) => void,
 *   createLayer:      (name, w, h) => object,
 *   renderLayerPanel: () => void,
 *   composite:        () => void,
 *   renderLayer?:     (layer) => HTMLCanvasElement,
 *   uiModule:         object,
 * }} deps
 */
import { state } from './state.js';

function _renderSource(layer, renderLayer) {
  if (!layer) return null;
  try {
    return typeof renderLayer === 'function' ? (renderLayer(layer) || layer.canvas) : layer.canvas;
  } catch {
    return layer.canvas;
  }
}

function _clearBakedAdjustments(layer) {
  if (!layer) return;
  layer.adjLayers = [];
  layer._adjFinal = null;
  layer._adjFinalKey = '';
  layer._adjCache = null;
  layer._adjCacheKey = '';
}

export function mergeLayerDownAtIndex(idx, renderLayer = null) {
  if (idx < 1 || idx >= state.layers.length) return null;
  const upper = state.layers[idx];
  const lower = state.layers[idx - 1];
  const upperOff = state.layerOffsets.get(upper.id) || { x: 0, y: 0 };
  const lowerOff = state.layerOffsets.get(lower.id) || { x: 0, y: 0 };
  const lowerSource = _renderSource(lower, renderLayer);
  const upperSource = _renderSource(upper, renderLayer);
  const merged = document.createElement('canvas');
  merged.width = state.imgWidth;
  merged.height = state.imgHeight;
  const mctx = merged.getContext('2d');
  mctx.globalAlpha = lower.opacity;
  mctx.drawImage(lowerSource, lowerOff.x, lowerOff.y);
  mctx.globalAlpha = upper.opacity;
  mctx.drawImage(upperSource, upperOff.x, upperOff.y);
  mctx.globalAlpha = 1;
  lower.canvas = merged;
  lower.ctx = lower.canvas.getContext('2d');
  lower.opacity = 1;
  lower.visible = true;
  state.layerOffsets.set(lower.id, { x: 0, y: 0 });
  _clearBakedAdjustments(lower);
  state.layers.splice(idx, 1);
  state.layerOffsets.delete(upper.id);
  state.activeLayerId = lower.id;
  return lower;
}

export function wireMergeButtons({ saveState, createLayer, renderLayerPanel, composite, renderLayer, uiModule }) {
  // Flatten Copy.
  document.getElementById('ge-flatten')?.addEventListener('click', () => {
    if (state.layers.length < 2) return;
    saveState('Flatten copy');
    const merged = createLayer('Flattened', state.imgWidth, state.imgHeight);
    const ctx = merged.ctx;
    for (const l of state.layers) {
      if (!l.visible) continue;
      const off = state.layerOffsets.get(l.id) || { x: 0, y: 0 };
      ctx.globalAlpha = l.opacity;
      ctx.drawImage(_renderSource(l, renderLayer), off.x, off.y);
      ctx.globalAlpha = 1;
    }
    _clearBakedAdjustments(merged);
    state.layers.push(merged);
    state.activeLayerId = merged.id;
    renderLayerPanel();
    composite();
    uiModule.showToast('Flattened copy created');
  });

  // Merge All — drop hidden layers; base = lowest visible.
  document.getElementById('ge-merge-all')?.addEventListener('click', () => {
    const visibleLayers = state.layers.filter(l => l.visible);
    if (visibleLayers.length < 2) {
      if (uiModule) uiModule.showToast('Need at least two visible layers to merge');
      return;
    }
    saveState('Merge all');
    const base = visibleLayers[0];
    const merged = document.createElement('canvas');
    merged.width = state.imgWidth;
    merged.height = state.imgHeight;
    const baseCtx = merged.getContext('2d');
    for (let i = 0; i < visibleLayers.length; i++) {
      const l = visibleLayers[i];
      const off = state.layerOffsets.get(l.id) || { x: 0, y: 0 };
      baseCtx.globalAlpha = l.opacity;
      baseCtx.drawImage(_renderSource(l, renderLayer), off.x, off.y);
      baseCtx.globalAlpha = 1;
    }
    base.canvas = merged;
    base.ctx = base.canvas.getContext('2d');
    base.opacity = 1;
    base.visible = true;
    state.layerOffsets.set(base.id, { x: 0, y: 0 });
    _clearBakedAdjustments(base);
    // Free offset entries for the discarded layers; keep base.
    for (const l of state.layers) {
      if (l === base) continue;
      state.layerOffsets.delete(l.id);
    }
    state.layers = [base];
    state.activeLayerId = base.id;
    renderLayerPanel();
    composite();
    uiModule.showToast('Visible layers merged');
  });

  // Merge Down.
  document.getElementById('ge-merge-down')?.addEventListener('click', () => {
    const idx = state.layers.findIndex(l => l.id === state.activeLayerId);
    if (idx < 1) return; // can't merge the bottom layer
    saveState('Merge down');
    mergeLayerDownAtIndex(idx, renderLayer);
    renderLayerPanel();
    composite();
    uiModule.showToast('Layer merged down');
  });
}
