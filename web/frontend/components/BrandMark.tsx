export function DivergeMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 96 96" className={className} fill="none" aria-hidden="true">
      <path
        d="M21.5 65.5a34.5 34.5 0 1 1 53 0"
        stroke="currentColor"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d="M48 78V45M48 45 31 28M48 45l17-17"
        stroke="currentColor"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M26.5 23.5 42 28l-11 11-1.5-8.5-8.5-1.5 5.5-5.5Z" fill="currentColor" />
      <path d="M69.5 23.5 54 28l11 11 1.5-8.5 8.5-1.5-5.5-5.5Z" fill="currentColor" />
      <path
        d="M48 78c-8.8-7.8-18.6-12.1-31.4-12.1M48 78c8.8-7.8 18.6-12.1 31.4-12.1M48 72.8c-10.2-6.4-21.1-9.2-32.8-8.3M48 72.8c10.2-6.4 21.1-9.2 32.8-8.3M48 67.6c-9.1-4.4-18.4-6.4-28-5.8M48 67.6c9.1-4.4 18.4-6.4 28-5.8"
        stroke="currentColor"
        strokeWidth="3.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
