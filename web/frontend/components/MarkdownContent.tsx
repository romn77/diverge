"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { HighlightCards } from "@/components/HighlightCards";
import { parseHighlights, stripHighlightsBlocks } from "@/lib/highlights";

interface MarkdownContentProps {
  content: string;
  isLoading?: boolean;
  highlightMode?: "single" | "off";
}

function LoadingSkeleton({ label }: { label: string }) {
  return (
    <div
      className="animate-pulse space-y-4"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div className="h-8 w-3/4 rounded bg-slate-200"></div>
      <div className="h-4 w-full rounded bg-slate-200"></div>
      <div className="h-4 w-5/6 rounded bg-slate-200"></div>
      <div className="h-4 w-4/5 rounded bg-slate-200"></div>
    </div>
  );
}

/**
 * Renders markdown content with GFM table support and prose styling.
 * Memoized to avoid re-renders from parent state changes.
 */
export const MarkdownContent = React.memo(
  function MarkdownContent({
    content,
    isLoading = false,
    highlightMode = "single",
  }: MarkdownContentProps) {
    const { processedContent, highlights } = useMemo(() => {
      if (highlightMode === "single") {
        const parsed = parseHighlights(content);
        return {
          processedContent: parsed.cleanMarkdown,
          highlights: parsed.highlights,
        };
      }

      return {
        processedContent: stripHighlightsBlocks(content),
        highlights: null,
      };
    }, [content, highlightMode]);

    const hasContent = processedContent.trim().length > 0;
    const showOverlay = isLoading && hasContent;

    if (isLoading && !hasContent) {
      return (
        <LoadingSkeleton label="Loading report content" />
      );
    }

    return (
      <div className="relative">
        {highlights && <HighlightCards highlights={highlights} />}
        <article
          className="markdown-content max-w-none"
          aria-busy={isLoading}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {processedContent}
          </ReactMarkdown>
        </article>

        {showOverlay && (
          <div className="pointer-events-none absolute inset-0 rounded-xl bg-white p-4 md:p-6">
            <LoadingSkeleton label="Refreshing report content" />
          </div>
        )}
      </div>
    );
  }
);
