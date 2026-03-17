import { ReportHighlights, TradeSignal } from "@/lib/highlights";
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
      return "terminal-hero--buy";
    case "HOLD":
      return "terminal-hero--hold";
    case "SELL":
      return "terminal-hero--sell";
    default:
      return "";
  }
}

function renderEntryBody(entry: TerminalEntry) {
  if (!entry.body) {
    return null;
  }

  return <p className="terminal-entry-body">{entry.body}</p>;
}

function renderStoryPanel(panel: TerminalPanel) {
  if (!panel.summary) {
    return null;
  }

  return <p className="terminal-story">{panel.summary}</p>;
}

function renderColumnsPanel(panel: TerminalPanel) {
  return (
    <div className="terminal-columns">
      {panel.columns?.map((column) => (
        <div key={column.title} className="terminal-column">
          <div className="terminal-column-header">{column.title}</div>
          <ul className="terminal-column-list">
            {column.items.map((item, idx) => (
              <li key={`${column.title}-${idx}`}>{item}</li>
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
    <div className="terminal-table-wrap">
      <table className="terminal-table">
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
    <div className="terminal-matrix">
      {panel.entries?.map((entry, idx) => (
        <article
          key={`${entry.title}-${idx}`}
          className="terminal-matrix-card"
        >
          <p className="terminal-matrix-label">{entry.title}</p>
          {entry.body && <p className="terminal-matrix-value">{entry.body}</p>}
          {entry.meta && <p className="terminal-matrix-meta">{entry.meta}</p>}
        </article>
      ))}
    </div>
  );
}

function renderBulletPanel(panel: TerminalPanel) {
  return (
    <ul className="terminal-list">
      {panel.entries?.map((entry, idx) => (
        <li key={`${entry.title}-${idx}`} className="terminal-list-item">
          <div className="terminal-list-copy">
            <p className="terminal-entry-title">{entry.title}</p>
            {renderEntryBody(entry)}
          </div>
        </li>
      ))}
    </ul>
  );
}

function renderQueuePanel(panel: TerminalPanel) {
  return (
    <ol className="terminal-queue">
      {panel.entries?.map((entry, idx) => (
        <li key={`${entry.title}-${idx}`} className="terminal-queue-item">
          <div className="terminal-queue-copy">
            <div className="terminal-queue-row">
              <p className="terminal-entry-title">{entry.title}</p>
              {entry.meta && (
                <span className="terminal-inline-badge">
                  {entry.meta}
                </span>
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

  return (
    <section className="highlights-container terminal-deck" aria-label="Structured report highlights">
      <header className={`terminal-hero ${heroSignalClass(deck.signal)}`}>
        <div className="terminal-hero-top">
          <div className="terminal-hero-copy">
            <div className="terminal-title-row">
              <h3 className="terminal-hero-title">{deck.heroTitle}</h3>
              <span className="terminal-category">{deck.categoryLabel}</span>
            </div>
          </div>

          <div className="terminal-hero-status">
            <p className={`signal-badge terminal-signal ${signalClass(deck.signal)}`}>{deck.signal}</p>
            {deck.confidence && (
              <p className="terminal-confidence">Confidence {deck.confidence}</p>
            )}
          </div>
        </div>

        <p className="terminal-summary">{deck.summary}</p>

        <div className="terminal-chip-strip">
          {deck.heroChips.map((chip) => (
            <article
              key={`${chip.label}-${chip.value}`}
              className="terminal-chip"
            >
              <p className="terminal-chip-label">{chip.label}</p>
              <p className="terminal-chip-value">{chip.value}</p>
            </article>
          ))}
        </div>
      </header>

      <div className="highlights-grid terminal-console-grid">
        {deck.consoles.map((consolePanel) => (
          <section
            key={consolePanel.key}
            className="terminal-console"
            aria-label={consolePanel.title}
          >
            <div className="terminal-console-body">
              {consolePanel.panels.map((panel) => (
                <section
                  key={panel.key}
                  className="terminal-panel"
                  aria-label={panel.title}
                >
                  <div className="terminal-panel-header">
                    <h5>{panel.title}</h5>
                  </div>
                  {renderPanelContent(panel)}
                </section>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
