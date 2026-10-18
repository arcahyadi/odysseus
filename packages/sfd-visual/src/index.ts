/**
 * @agentos/sfd-visual — Visual Output Engine
 * ADR-003 compliant plugin
 *
 * Diagrams (Mermaid/PlantUML via Kroki), visual reports, UI mockups.
 * Output modalities: SVG inline, PNG file, HTML interactive.
 * SFD Principle P22: Visual Output Modality.
 */

import type { SFDPlugin, PluginConfig, SFDPhase, PhaseContext, PhaseResult, SFDEvent } from "../../types";
import * as fs from "fs";
import * as path from "path";
import * as zlib from "zlib";

// ============================================================================
// Types
// ============================================================================

export type DiagramType = "mermaid" | "plantuml" | "graphviz" | "d2" | "blockdiag" | "nomnoml" | "c4plantuml";

export type OutputModality = "svg-inline" | "png-file" | "html-interactive";

export type ReportFormat = "bar" | "line" | "pie" | "radar" | "scatter" | "table" | "dashboard";

export interface RenderDiagramOptions {
  type: DiagramType;
  code: string;
  modality?: OutputModality;
  title?: string;
  outputPath?: string;
}

export interface GenerateReportOptions {
  data: Record<string, any>[];
  format: ReportFormat;
  modality?: OutputModality;
  title?: string;
  width?: number;
  height?: number;
  outputPath?: string;
}

export interface RenderMockupOptions {
  spec: Record<string, any>;
  modality?: OutputModality;
  template?: string;
  outputPath?: string;
}

export interface VisualOutput {
  mimeType: string;
  modality: OutputModality;
  content: string;
  filePath?: string;
  metadata: {
    generatedAt: string;
    engine: string;
    sizeBytes: number;
  };
}

// ============================================================================
// Kroki client
// ============================================================================

const KROKI_BASE = "https://kroki.io";

const KROKI_ENDPOINTS: Record<DiagramType, string> = {
  mermaid: "mermaid",
  plantuml: "plantuml",
  graphviz: "graphviz",
  d2: "d2",
  blockdiag: "blockdiag",
  nomnoml: "nomnoml",
  c4plantuml: "c4plantuml",
};

class VisualOutputEngine {
  private eventBus: any | null = null;
  private outputDir: string;
  private defaultModality: OutputModality;

  constructor(outputDir: string = "data/visual-output") {
    this.outputDir = outputDir;
    this.defaultModality = "svg-inline";
    if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });
  }

  setEventBus(bus: any) {
    this.eventBus = bus;
  }

  private emit(eventType: string, data: Record<string, any>) {
    if (this.eventBus) {
      try {
        this.eventBus.emit("sfd-visual", eventType, data);
      } catch {
        // EventBus not required for core functionality
      }
    }
  }

  // =========================================================================
  // Core: Render Diagram
  // =========================================================================

  async renderDiagram(options: RenderDiagramOptions): Promise<VisualOutput> {
    const { type, code, modality = this.defaultModality, title, outputPath } = options;
    const endpoint = KROKI_ENDPOINTS[type];
    if (!endpoint) throw new Error(`Unsupported diagram type: ${type}`);

    const start = Date.now();
    this.emit("diagram.render", { type, title, modality, codeSize: code.length });

    let svgContent: string;

    if (process.env["KROKI_ENABLED"] !== "false") {
      svgContent = await this.fetchKroki(endpoint, code, "svg");
    } else {
      svgContent = this.generateInlineSVG(type, code, title);
    }

    const result = this.formatOutput(svgContent, modality, "image/svg+xml", outputPath, title);

    this.emit("diagram.rendered", {
      type,
      modality: result.modality,
      durationMs: Date.now() - start,
      sizeBytes: result.metadata.sizeBytes,
    });

    return result;
  }

  private async fetchKroki(endpoint: string, code: string, format: string): Promise<string> {
    const url = `${KROKI_BASE}/${endpoint}/${format}`;
    const body = typeof TextEncoder !== "undefined"
      ? new TextEncoder().encode(code)
      : Buffer.from(code, "utf-8");
    const compressed = zlib.deflateRawSync(body);
    const encoded = Buffer.from(compressed).toString("base64url");

    try {
      const response = await fetch(`${url}/${encoded}`);
      if (!response.ok) throw new Error(`Kroki returned ${response.status}`);
      return await response.text();
    } catch {
      return `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100">
        <rect width="400" height="100" fill="#fff3cd" stroke="#ffc107" rx="4"/>
        <text x="200" y="55" text-anchor="middle" font-family="monospace" font-size="12" fill="#856404">
          Kroki unavailable — rendering offline
        </text>
      </svg>`;
    }
  }

  private generateInlineSVG(type: DiagramType, code: string, title?: string): string {
    const safeCode = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300">
  <rect width="600" height="300" fill="#f8f9fa" stroke="#dee2e6" rx="6"/>
  <text x="300" y="30" text-anchor="middle" font-family="monospace" font-size="14" font-weight="bold" fill="#495057">
    ${title || type.toUpperCase() + " Diagram"}
  </text>
  <rect x="20" y="50" width="560" height="220" fill="#ffffff" stroke="#adb5bd" rx="4"/>
  ${this.wrapCodeLines(safeCode, 30, 70, 560)}
</svg>`;
  }

  private wrapCodeLines(code: string, startX: number, startY: number, maxWidth: number): string {
    const lines = code.split("\n");
    const lineHeight = 14;
    const charsPerLine = Math.floor(maxWidth / 7);
    let svg = "";
    for (let i = 0; i < Math.min(lines.length, 15); i++) {
      const truncated = lines[i].length > charsPerLine
        ? lines[i].substring(0, charsPerLine - 3) + "..."
        : lines[i];
      svg += `\n  <text x="${startX}" y="${startY + i * lineHeight}" font-family="monospace" font-size="10" fill="#212529">${truncated}</text>`;
    }
    return svg;
  }

  // =========================================================================
  // Core: Generate Visual Report
  // =========================================================================

  async generateReport(options: GenerateReportOptions): Promise<VisualOutput> {
    const { data, format, modality = this.defaultModality, title, width = 800, height = 500, outputPath } = options;
    const start = Date.now();

    this.emit("report.generate", { format, title, modality, rows: data.length });

    let content: string;
    switch (format) {
      case "dashboard":
        content = this.renderDashboard(data, title, width, height);
        break;
      case "table":
        content = this.renderTable(data, title, width);
        break;
      default:
        content = this.renderChart(format, data, title, width, height);
    }

    const mimeType = modality === "html-interactive" ? "text/html" : "image/svg+xml";
    const result = this.formatOutput(content, modality, mimeType, outputPath, title);

    this.emit("report.generated", {
      format,
      modality: result.modality,
      durationMs: Date.now() - start,
      sizeBytes: result.metadata.sizeBytes,
    });

    return result;
  }

  private renderChart(format: ReportFormat, data: Record<string, any>[], title?: string, w = 800, h = 500): string {
    const colors = ["#4361ee", "#3a0ca3", "#7209b7", "#f72585", "#4cc9f0", "#2ec4b6", "#ff9f1c", "#e71d36"];
    const keys = data.length > 0 ? Object.keys(data[0]) : [];
    const labelKey = keys[0] || "label";
    const valueKey = keys[1] || "value";
    const margin = { top: 40, right: 40, bottom: 60, left: 60 };
    const chartW = w - margin.left - margin.right;
    const chartH = h - margin.top - margin.bottom;

    let bodies = "";
    const maxVal = Math.max(...data.map(d => Number(d[valueKey]) || 0), 1);

    if (format === "bar") {
      const barGap = 4;
      const barCount = data.length;
      const barW = Math.max(4, (chartW - barGap * (barCount - 1)) / barCount);
      data.forEach((d, i) => {
        const val = Number(d[valueKey]) || 0;
        const barH = (val / maxVal) * (chartH - 20);
        const x = margin.left + i * (barW + barGap);
        const y = margin.top + chartH - barH;
        bodies += `<rect x="${x}" y="${y}" width="${barW}" height="${barH}" fill="${colors[i % colors.length]}" rx="2">
          <title>${d[labelKey]}: ${val}</title></rect>`;
        bodies += `<text x="${x + barW / 2}" y="${y - 6}" text-anchor="middle" font-size="10" fill="#495057">${val}</text>`;
        bodies += `<text x="${x + barW / 2}" y="${margin.top + chartH + 16}" text-anchor="middle" font-size="10" fill="#495057" transform="rotate(-30,${x + barW / 2},${margin.top + chartH + 16})">${d[labelKey]}</text>`;
      });
    } else if (format === "line") {
      const pts = data.map((d, i) => {
        const x = margin.left + (i / Math.max(data.length - 1, 1)) * chartW;
        const y = margin.top + chartH - ((Number(d[valueKey]) || 0) / maxVal) * chartH;
        return { x, y, label: d[labelKey], val: Number(d[valueKey]) || 0 };
      });
      const pathD = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
      bodies += `<path d="${pathD}" fill="none" stroke="${colors[0]}" stroke-width="2"/>`;
      pts.forEach(p => {
        bodies += `<circle cx="${p.x}" cy="${p.y}" r="4" fill="${colors[0]}"><title>${p.label}: ${p.val}</title></circle>`;
        bodies += `<text x="${p.x}" y="${p.y - 10}" text-anchor="middle" font-size="10" fill="#495057">${p.val}</text>`;
        bodies += `<text x="${p.x}" y="${margin.top + chartH + 16}" text-anchor="middle" font-size="10" fill="#495057">${p.label}</text>`;
      });
    } else if (format === "pie") {
      const total = data.reduce((s, d) => s + (Number(d[valueKey]) || 0), 0) || 1;
      const cx = margin.left + chartW / 2;
      const cy = margin.top + chartH / 2;
      const r = Math.min(chartW, chartH) / 2 - 20;
      let angle = -Math.PI / 2;
      data.forEach((d, i) => {
        const val = Number(d[valueKey]) || 0;
        const slice = (val / total) * Math.PI * 2;
        const x1 = cx + r * Math.cos(angle);
        const y1 = cy + r * Math.sin(angle);
        const x2 = cx + r * Math.cos(angle + slice);
        const y2 = cy + r * Math.sin(angle + slice);
        const large = slice > Math.PI ? 1 : 0;
        bodies += `<path d="M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z" fill="${colors[i % colors.length]}" stroke="#fff" stroke-width="1"><title>${d[labelKey]}: ${val} (${Math.round(val / total * 100)}%)</title></path>`;
        angle += slice;
      });
      let legendY = margin.top + chartH + 16;
      data.forEach((d, i) => {
        bodies += `<rect x="${margin.left}" y="${legendY}" width="10" height="10" fill="${colors[i % colors.length]}"/>`;
        bodies += `<text x="${margin.left + 14}" y="${legendY + 9}" font-size="10" fill="#495057">${d[labelKey]}: ${d[valueKey]}</text>`;
        legendY += 14;
      });
    } else if (format === "radar") {
      const axes = keys.filter(k => k !== labelKey);
      const cx = margin.left + chartW / 2;
      const cy = margin.top + chartH / 2;
      const r = Math.min(chartW, chartH) / 2 - 30;
      const n = axes.length;
      data.forEach((d, rowIdx) => {
        let pathD = "";
        axes.forEach((axis, i) => {
          const val = (Number(d[axis]) || 0) / (maxVal || 1);
          const angle = -Math.PI / 2 + (2 * Math.PI * i) / n;
          const px = cx + r * val * Math.cos(angle);
          const py = cy + r * val * Math.sin(angle);
          pathD += `${i === 0 ? "M" : "L"}${px},${py}`;
        });
        pathD += "Z";
        bodies += `<path d="${pathD}" fill="${colors[rowIdx % colors.length]}" fill-opacity="0.3" stroke="${colors[rowIdx % colors.length]}" stroke-width="1.5"/>`;
      });
      axes.forEach((axis, i) => {
        const angle = -Math.PI / 2 + (2 * Math.PI * i) / n;
        const lx = cx + (r + 15) * Math.cos(angle);
        const ly = cy + (r + 15) * Math.sin(angle);
        bodies += `<text x="${lx}" y="${ly}" text-anchor="middle" font-size="10" fill="#495057">${axis}</text>`;
      });
    } else if (format === "scatter") {
      const xKey = keys[1] || "x";
      const yKey = keys[2] || "y";
      const xMax = Math.max(...data.map(d => Number(d[xKey]) || 0), 1);
      const yMax = Math.max(...data.map(d => Number(d[yKey]) || 0), 1);
      data.forEach((d, i) => {
        const sx = margin.left + ((Number(d[xKey]) || 0) / xMax) * chartW;
        const sy = margin.top + chartH - ((Number(d[yKey]) || 0) / yMax) * chartH;
        bodies += `<circle cx="${sx}" cy="${sy}" r="5" fill="${colors[i % colors.length]}"><title>${d[labelKey]} (${d[xKey]}, ${d[yKey]})</title></circle>`;
      });
    }

    return this.svgShell(title || `${format.toUpperCase()} Chart`, w, h, bodies);
  }

  private renderDashboard(data: Record<string, any>[], title?: string, w = 1200, h = 800): string {
    const sections: string[] = [];
    const cols = 2;
    const cellW = Math.floor((w - 60) / cols);
    const cellH = Math.floor((h - 100) / Math.ceil(3 / cols));

    const metrics = data.length > 0 ? Object.keys(data[0]).filter(k => typeof data[0][k] === "number") : [];
    const labels = data.length > 0 ? Object.keys(data[0]).filter(k => typeof data[0][k] !== "number") : [];

    let y = 50;
    let x = 20;

    data.forEach((row, i) => {
      const cx = x + cellW / 2;
      const cy = y + cellH / 2;

      sections.push(`<rect x="${x}" y="${y}" width="${cellW - 10}" height="${cellH - 10}" fill="#ffffff" stroke="#dee2e6" rx="8"/>`);
      sections.push(`<text x="${cx}" y="${y + 24}" text-anchor="middle" font-size="12" font-weight="bold" fill="#495057">${row[labels[0]] || `Card ${i + 1}`}</text>`);

      let my = y + 50;
      metrics.forEach((m, mi) => {
        sections.push(`<text x="${x + 24}" y="${my}" font-size="12" fill="#6c757d">${m}</text>`);
        sections.push(`<text x="${x + cellW - 40}" y="${my}" text-anchor="end" font-size="18" font-weight="bold" fill="#4361ee">${row[m]}</text>`);
        my += 28;
      });

      x += cellW;
      if (x + cellW > w) {
        x = 20;
        y += cellH;
      }
    });

    return this.svgShell(title || "Dashboard", w, h, sections.join("\n"));
  }

  private renderTable(data: Record<string, any>[], title?: string, w = 800): string {
    const keys = data.length > 0 ? Object.keys(data[0]) : [];
    const rowH = 24;
    const colW = Math.floor((w - 40) / keys.length);
    const h = 40 + (data.length + 1) * rowH + 20;
    const darkRows = ['<rect x="20" y="${40 + (i + 1) * rowH}" width="${w - 40}" height="${rowH}" fill="${i % 2 === 0 ? "#f8f9fa" : "white"}"/>'];

    let html = "";
    html += `<rect x="20" y="40" width="${w - 40}" height="${rowH}" fill="#4361ee" rx="2"/>`;

    keys.forEach((k, ci) => {
      html += `<text x="${30 + ci * colW}" y="57" font-size="12" font-weight="bold" fill="white">${k}</text>`;
    });

    data.forEach((row, ri) => {
      const y = 40 + (ri + 1) * rowH;
      html += `<rect x="20" y="${y}" width="${w - 40}" height="${rowH}" fill="${ri % 2 === 0 ? '#f8f9fa' : '#ffffff'}"/>`;
      keys.forEach((k, ci) => {
        html += `<text x="${30 + ci * colW}" y="${y + 17}" font-size="11" fill="#212529">${String(row[k] ?? "").substring(0, 30)}</text>`;
      });
      html += `<line x1="20" y1="${y + rowH}" x2="${w - 20}" y2="${y + rowH}" stroke="#dee2e6" stroke-width="0.5"/>`;
    });

    return this.svgShell(title || "Table", w, h, html);
  }

  private svgShell(title: string, w: number, h: number, body: string): string {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
  <rect width="${w}" height="${h}" fill="#f8f9fa"/>
  <text x="${w / 2}" y="24" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#212529">${title}</text>
  ${body}
</svg>`;
  }

  // =========================================================================
  // Core: Render UI Mockup
  // =========================================================================

  async renderMockup(options: RenderMockupOptions): Promise<VisualOutput> {
    const { spec, modality = this.defaultModality, template, outputPath } = options;
    const start = Date.now();

    this.emit("mockup.render", { modality, hasTemplate: !!template });

    const title = spec.title || spec.name || "UI Mockup";
    const components = spec.components || spec.elements || [];

    let content: string;
    if (modality === "html-interactive") {
      content = this.renderMockupHTML(title, components);
    } else {
      content = this.renderMockupSVG(title, components, 800, 600);
    }

    const mimeType = modality === "html-interactive" ? "text/html" : "image/svg+xml";
    const result = this.formatOutput(content, modality, mimeType, outputPath, title);

    this.emit("mockup.rendered", {
      modality: result.modality,
      durationMs: Date.now() - start,
      componentCount: components.length,
    });

    return result;
  }

  private renderMockupSVG(title: string, components: any[], w = 800, h = 600): string {
    let body = `<rect x="40" y="60" width="${w - 80}" height="${h - 140}" fill="#ffffff" stroke="#dee2e6" stroke-width="2" rx="8"/>`;
    body += `<text x="${w / 2}" y="85" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="#212529">${title}</text>`;

    let y = 110;
    const xStart = 60;

    components.forEach((comp, i) => {
      const compType = comp.type || "text";
      const compLabel = comp.label || comp.text || compType;
      const compW = comp.width || w - 120;
      const compH = comp.height || 28;

      if (y + compH > h - 60) return;

      switch (compType) {
        case "button":
          body += `<rect x="${xStart}" y="${y}" width="${compW}" height="${compH}" fill="#4361ee" rx="4"/>`;
          body += `<text x="${xStart + compW / 2}" y="${y + compH / 2 + 4}" text-anchor="middle" font-size="12" fill="white">${compLabel}</text>`;
          break;
        case "input":
        case "textfield":
          body += `<rect x="${xStart}" y="${y}" width="${compW}" height="${compH}" fill="white" stroke="#adb5bd" rx="4"/>`;
          body += `<text x="${xStart + 8}" y="${y + compH / 2 + 4}" font-size="11" fill="#6c757d">${compLabel}</text>`;
          break;
        case "image":
          body += `<rect x="${xStart}" y="${y}" width="${compW}" height="${compH}" fill="#e9ecef" stroke="#dee2e6" rx="4" stroke-dasharray="4"/>`;
          body += `<text x="${xStart + compW / 2}" y="${y + compH / 2 + 4}" text-anchor="middle" font-size="11" fill="#6c757d">[${compLabel}]</text>`;
          break;
        case "card":
        case "panel":
          body += `<rect x="${xStart}" y="${y}" width="${compW}" height="${compH}" fill="white" stroke="#dee2e6" rx="6"/>`;
          body += `<text x="${xStart + 12}" y="${y + 20}" font-size="12" font-weight="bold" fill="#212529">${compLabel}</text>`;
          if (comp.description) {
            body += `<text x="${xStart + 12}" y="${y + 36}" font-size="10" fill="#6c757d">${comp.description}</text>`;
          }
          break;
        case "navbar":
          body += `<rect x="0" y="60" width="${w}" height="${compH}" fill="#212529"/>`;
          body += `<text x="16" y="${60 + compH / 2 + 4}" font-size="13" font-weight="bold" fill="white">${compLabel}</text>`;
          break;
        default:
          body += `<text x="${xStart}" y="${y + compH / 2 + 4}" font-size="12" fill="#212529">${compLabel}</text>`;
      }

      y += compH + 8;
    });

    return this.svgShell(title, w, h, body);
  }

  private renderMockupHTML(title: string, components: any[]): string {
    const items = components.map(c => {
      const t = c.type || "text";
      const label = c.label || c.text || t;
      switch (t) {
        case "button":
          return `<button style="background:#4361ee;color:white;border:none;padding:8px 16px;border-radius:4px;cursor:pointer">${label}</button>`;
        case "input":
        case "textfield":
          return `<input placeholder="${label}" style="padding:8px;border:1px solid #adb5bd;border-radius:4px;width:100%;box-sizing:border-box"/>`;
        case "image":
          return `<div style="background:#e9ecef;border:1px dashed #dee2e6;border-radius:4px;height:120px;display:flex;align-items:center;justify-content:center;color:#6c757d">[${label}]</div>`;
        case "card":
        case "panel":
          return `<div style="background:white;border:1px solid #dee2e6;border-radius:6px;padding:16px"><strong>${label}</strong>${c.description ? `<p style="color:#6c757d;margin:4px 0 0">${c.description}</p>` : ""}</div>`;
        case "navbar":
          return `<nav style="background:#212529;color:white;padding:12px 16px;margin:-16px -16px 16px"><strong>${label}</strong></nav>`;
        case "heading":
          return `<h2 style="margin:0;color:#212529">${label}</h2>`;
        case "paragraph":
          return `<p style="color:#495057">${label}</p>`;
        default:
          return `<span>${label}</span>`;
      }
    }).join("\n    ");

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>${title}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 16px; background: #f8f9fa; color: #212529; }
    .mockup-container { max-width: 800px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; padding: 16px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .mockup-title { font-size: 18px; font-weight: bold; margin-bottom: 8px; }
  </style>
</head>
<body>
  <div class="mockup-container">
    <div class="mockup-title">${title}</div>
    ${items}
  </div>
</body>
</html>`;
  }

  // =========================================================================
  // Output formatting
  // =========================================================================

  private formatOutput(content: string, modality: OutputModality, mimeType: string, outputPath?: string, title?: string): VisualOutput {
    const generatedAt = new Date().toISOString();

    switch (modality) {
      case "png-file": {
        const p = outputPath || path.join(this.outputDir, `${title || "output"}-${Date.now()}.svg`);
        fs.writeFileSync(p, content, "utf-8");
        return {
          mimeType: "image/svg+xml",
          modality: "png-file",
          content: "",
          filePath: p,
          metadata: { generatedAt, engine: "@agentos/sfd-visual", sizeBytes: Buffer.byteLength(content, "utf-8") },
        };
      }
      case "html-interactive": {
        const p = outputPath || path.join(this.outputDir, `${title || "output"}-${Date.now()}.html`);
        fs.writeFileSync(p, content, "utf-8");
        return {
          mimeType,
          modality: "html-interactive",
          content,
          filePath: p,
          metadata: { generatedAt, engine: "@agentos/sfd-visual", sizeBytes: Buffer.byteLength(content, "utf-8") },
        };
      }
      case "svg-inline":
      default:
        return {
          mimeType,
          modality: "svg-inline",
          content,
          metadata: { generatedAt, engine: "@agentos/sfd-visual", sizeBytes: Buffer.byteLength(content, "utf-8") },
        };
    }
  }
}

// ============================================================================
// Singleton
// ============================================================================

let instance: VisualOutputEngine | null = null;
function getEngine(): VisualOutputEngine {
  if (!instance) instance = new VisualOutputEngine();
  return instance;
}

// ============================================================================
// Plugin: SFD Visual Output (ADR-003 compliant)
// ============================================================================

export const plugin: SFDPlugin = {
  name: "sfd-visual",
  version: "0.1.0",
  description: "Visual Output Engine — diagrams (Mermaid/PlantUML via Kroki), charts, dashboards, UI mockups. SVG/PNG/HTML output.",
  capabilities: [
    "visual.diagram",
    "visual.report",
    "visual.mockup",
    "visual.chart",
    "visual.dashboard",
    "visual.svg",
    "visual.png",
    "visual.html",
  ],

  async onActivate(config: PluginConfig) {
    const engine = getEngine();
    if (config.outputDir) (engine as any).outputDir = config.outputDir;
    if (config.eventBus) engine.setEventBus(config.eventBus);
  },

  async onDeactivate() {
    // No cleanup needed
  },

  async onPhase(phase: SFDPhase, context: PhaseContext): Promise<PhaseResult> {
    const start = Date.now();
    const engine = getEngine();

    if (phase === "design") {
      if (context.payload?.diagram) {
        const result = await engine.renderDiagram({
          type: context.payload.diagram.type || "mermaid",
          code: context.payload.diagram.code,
          modality: context.payload.diagram.modality,
          title: context.payload.diagram.title,
        });
        return {
          success: true,
          phase,
          output: { visual: result },
          metrics: { durationMs: Date.now() - start },
        };
      }
    }

    return {
      success: true,
      phase,
      output: { visual: true },
      metrics: { durationMs: Date.now() - start },
    };
  },
};

// ============================================================================
// Public API exports
// ============================================================================

export function renderDiagram(type: DiagramType, code: string, modality?: OutputModality): Promise<VisualOutput> {
  return getEngine().renderDiagram({ type, code, modality });
}

export function generateReport(options: GenerateReportOptions): Promise<VisualOutput> {
  return getEngine().generateReport(options);
}

export function renderMockup(spec: Record<string, any>, modality?: OutputModality): Promise<VisualOutput> {
  return getEngine().renderMockup({ spec, modality });
}

export { VisualOutputEngine };
