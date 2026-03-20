import { type ReportHighlights, type TradeSignal } from "@/lib/highlights";
import {
  buildHighlightDeck,
  type TerminalEntry,
  type TerminalPanel,
} from "@/lib/highlightTerminal";

interface HighlightCardsProps {
  highlights: ReportHighlights;
}

function signalClass(signal: TradeSignal): string {
  switch (signal) {
    case "BUY":
      return "signal-buy";
    case "HOLD":
      return "signal-hold";
    case "SELL":
      return "signal-sell";
    default:
      return "";
  }
}

function heroSignalClass(signal: TradeSignal): string {
  switch (signal) {
    case "BUY":
      return "summary-hero--buy";
    case "HOLD":
      return "summary-hero--hold";
    case "SELL":
      return "summary-hero--sell";
    default:
      return "";
  }
}

function renderEntryBody(entry: TerminalEntry) {
  if (!entry.body) {
    return null;
  }

  return <p className="summary-entry-body">{entry.body}</p>;
}

function renderStoryPanel(panel: TerminalPanel) {
  if (!panel.summary) {
    return null;
  }

  return <p className="summary-story">{panel.summary}</p>;
}

function renderColumnsPanel(panel: TerminalPanel) {
  return (
    <div className="summary-columns">
      {panel.columns?.map((column) => (
        <div key={column.title} className="summary-column">
          <p className="summary-column-title">{column.title}</p>
          <ul className="summary-column-list">
            {column.items.map((item, index) => (
              <li key={`${column.title}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function renderTablePanel(panel: TerminalPanel) {
  if (!panel.table) {
    return null;
  }

  return (
    <div className="summary-table-wrap">
      <table className="summary-table">
        <thead>
          <tr>
            {panel.table.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {panel.table.rows.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td>{row.value}</td>
              <td>{row.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderMatrixPanel(panel: TerminalPanel) {
  return (
    <div className="summary-matrix">
      {panel.entries?.map((entry, index) => (
        <article key={`${entry.title}-${index}`} className="summary-matrix-card">
          <p className="summary-matrix-label">{entry.title}</p>
          {entry.body && <p className="summary-matrix-value">{entry.body}</p>}
          {entry.meta && <p className="summary-matrix-meta">{entry.meta}</p>}
        </article>
      ))}
    </div>
  );
}

function renderBulletPanel(panel: TerminalPanel) {
  return (
    <ul className="summary-list">
      {panel.entries?.map((entry, index) => (
        <li key={`${entry.title}-${index}`} className="summary-list-item">
          <div className="summary-list-copy">
            <p className="summary-entry-title">{entry.title}</p>
            {renderEntryBody(entry)}
          </div>
        </li>
      ))}
    </ul>
  );
}

function renderQueuePanel(panel: TerminalPanel) {
  return (
    <ol className="summary-queue">
      {panel.entries?.map((entry, index) => (
        <li key={`${entry.title}-${index}`} className="summary-queue-item">
          <div className="summary-queue-copy">
            <div className="summary-queue-row">
              <p className="summary-entry-title">{entry.title}</p>
              {entry.meta && (
                <span className="summary-inline-badge">{entry.meta}</span>
              )}
            </div>
            {renderEntryBody(entry)}
          </div>
        </li>
      ))}
    </ol>
  );
}

function renderPanelContent(panel: TerminalPanel) {
  switch (panel.variant) {
    case "story":
      return renderStoryPanel(panel);
    case "columns":
      return renderColumnsPanel(panel);
    case "table":
      return renderTablePanel(panel);
    case "matrix":
      return renderMatrixPanel(panel);
    case "bullet":
      return renderBulletPanel(panel);
    case "queue":
      return renderQueuePanel(panel);
    default:
      return null;
  }
}

export function HighlightCards({ highlights }: HighlightCardsProps) {
  const deck = buildHighlightDeck(highlights);
  const panels = deck.consoles.flatMap((consolePanel) => consolePanel.panels);

  return (
    <section className="highlights-container summary-deck" aria-label="Structured report highlights">
      <header className={`summary-hero ${heroSignalClass(deck.signal)}`}>
        <div className="summary-hero-top">
          <div className="summary-hero-copy">
            <div className="summary-title-row">
              <h3 className="summary-hero-title">{deck.heroTitle}</h3>
              <span className="summary-category">{deck.categoryLabel}</span>
            </div>
          </div>

          <div className="summary-hero-status">
            <p className={`signal-badge summary-signal-badge ${signalClass(deck.signal)}`}>
              {deck.signal}
            </p>
            {deck.confidence && (
              <p className="summary-confidence">Confidence {deck.confidence}</p>
            )}
          </div>
        </div>

        <p className="summary-summary">{deck.summary}</p>

        <div className="summary-chip-row">
          {deck.heroChips.map((chip) => (
            <article key={`${chip.label}-${chip.value}`} className="summary-chip">
              <p className="summary-chip-label">{chip.label}</p>
              <p className="summary-chip-value">{chip.value}</p>
            </article>
          ))}
        </div>
      </header>

      <div className="summary-panels">
        {panels.map((panel) => (
          <section
            key={panel.key}
            className={`summary-panel${panel.span ? ` summary-panel--${panel.span}` : ""}`}
            aria-label={panel.title}
          >
            <p className="summary-panel-kicker">{panel.title}</p>
            {renderPanelContent(panel)}
          </section>
        ))}
      </div>
    </section>
  );
}
