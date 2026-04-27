"use client";

import React, { useMemo } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
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

function flattenText(node: React.ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (Array.isArray(node)) {
    return node.map(flattenText).join("");
  }

  if (React.isValidElement(node)) {
    const element = node as React.ReactElement<{ children?: React.ReactNode }>;
    return flattenText(element.props.children);
  }

  return "";
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\u4e00-\u9fff\s-]/g, "")
    .replace(/\s+/g, "-");
}

/**
 * Renders markdown content with reading-mode defaults and optional highlights.
 */
export const MarkdownContent = React.memo(function MarkdownContent({
  content,
  isLoading = false,
  highlightMode = "single",
}: MarkdownContentProps) {
  const { t } = usePreferences();
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

  const components = useMemo(
    () => ({
      h1: ({ children, ...props }: React.ComponentPropsWithoutRef<"h1">) => {
        const text = flattenText(children);
        const id = slugify(text);

        return (
          <h1 id={id} {...props}>
            {children}
          </h1>
        );
      },
      h2: ({ children, ...props }: React.ComponentPropsWithoutRef<"h2">) => {
        const text = flattenText(children);
        const id = slugify(text);

        return (
          <h2 id={id} {...props}>
            {children}
          </h2>
        );
      },
      h3: ({ children, ...props }: React.ComponentPropsWithoutRef<"h3">) => {
        const text = flattenText(children);
        const id = slugify(text);

        return (
          <h3 id={id} {...props}>
            {children}
          </h3>
        );
      },
      h4: ({ children, ...props }: React.ComponentPropsWithoutRef<"h4">) => {
        const text = flattenText(children);
        const id = slugify(text);

        return (
          <h4 id={id} {...props}>
            {children}
          </h4>
        );
      },
      table: ({ children, ...props }: React.ComponentPropsWithoutRef<"table">) => (
        <div
          className="min-w-0 max-w-full overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label={t("markdown.scrollableTable", "Scrollable table")}
        >
          <table {...props}>{children}</table>
        </div>
      ),
    }),
    [t]
  );

  const hasContent = processedContent.trim().length > 0;
  const showProgressBar = isLoading && hasContent;

  if (isLoading && !hasContent) {
    return (
      <LoadingSkeleton
        label={t("markdown.loadingContent", "Loading report content")}
      />
    );
  }

  return (
    <div className="relative min-w-0 w-full max-w-full space-y-12 overflow-hidden">
      {showProgressBar && (
        <div
          className="progress-slide pointer-events-none absolute inset-x-0 top-0 z-10 h-0.5 rounded-full bg-[var(--primary)]"
          aria-hidden
        />
      )}

      {highlights && <HighlightCards highlights={highlights} />}

      <article
        className="markdown-content min-w-0 w-full max-w-full"
        aria-busy={isLoading}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {processedContent}
        </ReactMarkdown>
      </article>
    </div>
  );
});
