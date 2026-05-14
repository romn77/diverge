export function DecisionCardSkeleton() {
  return (
    <section className="decision-card decision-card--loading" role="status" aria-live="polite">
      <div className="decision-card-skeleton decision-card-skeleton--title" />
      <div className="decision-card-skeleton-row">
        <div className="decision-card-skeleton" />
        <div className="decision-card-skeleton" />
        <div className="decision-card-skeleton" />
      </div>
      <div className="decision-card-skeleton decision-card-skeleton--body" />
    </section>
  );
}
