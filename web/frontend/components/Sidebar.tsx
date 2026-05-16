"use client";

import Link from "next/link";
import {
  type ReactNode,
  useEffect,
  useState,
} from "react";
import { usePathname } from "next/navigation";
import { Newspaper, Radar } from "lucide-react";
import { DivergeMark } from "@/components/BrandMark";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  buildActivityHref,
  buildAssetsHref,
  buildHomeHref,
  buildJournalHref,
  buildMarketBriefHref,
  buildOpportunitiesHref,
  buildScreenerHref,
} from "@/lib/workbenchRoutes";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({
  isOpen,
  onClose,
}: SidebarProps) {
  const pathname = usePathname();
  const { t } = usePreferences();
  const {
    activeOpportunityTasks,
    activeScreenerTasks,
    activeTasks,
    canAccessOpportunityRadar,
  } = useWorkbench();
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [isDesktopCollapsed, setIsDesktopCollapsed] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 767px)");
    const syncViewport = (event?: MediaQueryListEvent) => {
      setIsMobileViewport(event ? event.matches : mediaQuery.matches);
    };

    syncViewport();
    mediaQuery.addEventListener("change", syncViewport);
    return () => {
      mediaQuery.removeEventListener("change", syncViewport);
    };
  }, []);

  const isMobileDrawerOpen = isMobileViewport && isOpen;
  const isDesktopRail = !isMobileViewport && isDesktopCollapsed;
  const totalActive =
    activeTasks.length + activeScreenerTasks.length + activeOpportunityTasks.length;
  const analysisLabel = t("sidebar.nav.analysis", "Analysis");
  const marketBriefLabel = t("sidebar.nav.marketBrief", "Market Brief");
  const screenerLabel = t("sidebar.nav.screener", "Screener");
  const opportunityLabel = t("sidebar.nav.opportunities", "Opportunities");
  const assetsLabel = t("sidebar.nav.assets", "Assets");
  const journalLabel = t("sidebar.nav.journal", "Journal");
  const activityLabel = t("sidebar.nav.activity", "Activity");
  const workbenchNavigationLabel = t(
    "sidebar.workbenchNavigation",
    "Workbench navigation"
  );
  const isAnalysisActive = pathname === "/" || pathname.startsWith("/reports/");
  const isMarketBriefActive =
    pathname === buildMarketBriefHref() || pathname.startsWith("/market-briefs/");
  const isScreenerActive =
    pathname === buildScreenerHref() || pathname.startsWith("/screeners/");
  const isOpportunityActive =
    pathname === buildOpportunitiesHref() ||
    pathname.startsWith("/opportunities/") ||
    pathname.startsWith("/opportunity-tasks/");
  const isAssetsActive =
    pathname === buildAssetsHref() || pathname.startsWith("/assets/");
  const isJournalActive = pathname === buildJournalHref();
  const isActivityActive =
    pathname === buildActivityHref() ||
    pathname.startsWith("/tasks/") ||
    pathname.startsWith("/screener-tasks/") ||
    pathname.startsWith("/opportunity-tasks/");

  useEffect(() => {
    if (!isMobileDrawerOpen) {
      document.body.style.overflow = "";
      return;
    }

    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isMobileDrawerOpen]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }

      if (isMobileDrawerOpen) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileDrawerOpen, onClose]);

  const desktopDrawerClasses = [
    "sidebar-surface sidebar-surface--quiet hidden flex-col overflow-y-auto border-r border-[var(--border)] py-4 transition-[width,padding] duration-300 md:fixed md:left-0 md:top-0 md:z-[var(--z-sidebar)] md:flex md:h-[100svh] md:py-0",
    isDesktopCollapsed
      ? "md:w-[4.75rem] md:max-w-none md:px-2.5"
      : "md:w-[14.5rem] md:max-w-none md:px-3",
    "md:border-r-0",
  ].join(" ");
  const desktopShellClasses = [
    "hidden md:block md:shrink-0 md:transition-[width] md:duration-300 md:ease-[cubic-bezier(0.2,0.75,0.2,1)]",
    isDesktopCollapsed ? "md:w-[4.75rem]" : "md:w-[14.5rem]",
  ].join(" ");
  const headerClasses = [
    "border-b border-[var(--border)] py-2.5 md:py-0",
    isDesktopRail
      ? "flex flex-col items-center gap-2 md:py-3"
      : "h-16 flex items-center md:h-[var(--workbench-topbar-height)]",
  ].join(" ");
  const desktopToggleClasses = [
    "focus-ring hidden h-8 w-8 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface)] text-muted-foreground shadow-[var(--button-secondary-shadow)] transition active:translate-y-px motion-reduce:active:translate-y-0 hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)] hover:text-[var(--primary)] md:inline-flex",
    isDesktopRail ? "" : "ml-auto",
  ].join(" ");
  const collapseLabel = t("sidebar.collapse", "Collapse sidebar");
  const expandLabel = t("sidebar.expand", "Expand sidebar");
  const desktopToggleLabel = isDesktopCollapsed ? expandLabel : collapseLabel;

  const handleNavSelection = () => {
    if (isMobileDrawerOpen) {
      onClose();
    }
  };

  const toggleDesktopCollapse = () => {
    setIsDesktopCollapsed((current) => !current);
  };

  const sidebarBody = (
    <div className="flex min-h-full flex-col">
      <div className={headerClasses}>
        <Link href={buildHomeHref()} className="flex min-w-0 items-center gap-2">
          <div className="grid h-[2.15rem] w-[2.15rem] shrink-0 place-items-center rounded-md border border-[var(--border)] bg-[var(--surface-translucent)] text-[var(--primary)]">
            <DivergeMark className="h-6 w-6" />
          </div>
          {!isDesktopRail ? (
            <div className="min-w-0">
              <p className="font-heading text-[14px] font-bold leading-5 text-foreground">Diverge</p>
            </div>
          ) : null}
        </Link>

        {isMobileViewport ? (
          <Button
            type="button"
            variant="secondary"
            size="icon"
            className="ml-auto h-8 w-8 rounded-md md:hidden"
            onClick={onClose}
            aria-label={t("sidebar.closeSidebar", "Close sidebar")}
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
              <path
                d="M6 6l8 8M14 6l-8 8"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
              />
            </svg>
          </Button>
        ) : null}

        <button
          type="button"
          className={desktopToggleClasses}
          onClick={toggleDesktopCollapse}
          aria-label={desktopToggleLabel}
          aria-expanded={!isDesktopRail}
          title={desktopToggleLabel}
        >
          <svg
            viewBox="0 0 16 16"
            className={`h-4 w-4 transition-transform ${isDesktopRail ? "rotate-180" : ""}`}
            fill="none"
            aria-hidden
          >
            <path
              d="M9.5 3.5 5 8l4.5 4.5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M13 3.5 8.5 8 13 12.5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {isDesktopRail ? (
        <div className="mt-3 flex flex-1 flex-col items-center">
          <div className="flex flex-col items-center gap-1.5">
            <div className="flex flex-col items-center gap-1.5">
              <RailLinkButton
                href={buildHomeHref()}
                label={analysisLabel}
                title={analysisLabel}
                active={isAnalysisActive}
                onClick={handleNavSelection}
              >
                <AnalysisIcon />
              </RailLinkButton>
              <RailLinkButton
                href={buildMarketBriefHref()}
                label={marketBriefLabel}
                title={marketBriefLabel}
                active={isMarketBriefActive}
                onClick={handleNavSelection}
              >
                <Newspaper className="h-4 w-4" aria-hidden />
              </RailLinkButton>
              <RailLinkButton
                href={buildScreenerHref()}
                label={screenerLabel}
                title={screenerLabel}
                active={isScreenerActive}
                onClick={handleNavSelection}
              >
                <ScreenerIcon />
              </RailLinkButton>
              {canAccessOpportunityRadar ? (
                <RailLinkButton
                  href={buildOpportunitiesHref()}
                  label={opportunityLabel}
                  title={opportunityLabel}
                  active={isOpportunityActive}
                  onClick={handleNavSelection}
                >
                  <Radar className="h-4 w-4" aria-hidden />
                </RailLinkButton>
              ) : null}
            </div>

            <div className="my-1.5 flex justify-center" aria-hidden="true">
              <span className="h-px w-6 bg-[var(--divider-soft)]" />
            </div>

            <div className="flex flex-col items-center gap-1.5">
              <RailLinkButton
                href={buildAssetsHref()}
                label={assetsLabel}
                title={assetsLabel}
                active={isAssetsActive}
                onClick={handleNavSelection}
              >
                <AssetsIcon />
              </RailLinkButton>
              <RailLinkButton
                href={buildJournalHref()}
                label={journalLabel}
                title={journalLabel}
                active={isJournalActive}
                onClick={handleNavSelection}
              >
                <JournalIcon />
              </RailLinkButton>
            </div>
          </div>

          <div className="mt-auto mb-4 w-full border-t border-[var(--border)] pt-3">
            <div className="mb-2.5 flex justify-center" aria-hidden="true">
              <span className="h-4 w-px bg-[var(--divider-soft)]" />
            </div>
            <div className="flex justify-center">
              <RailLinkButton
                href={buildActivityHref()}
                label={activityLabel}
                title={activityLabel}
                active={isActivityActive}
                count={totalActive}
                onClick={handleNavSelection}
              >
                <ActivityIcon />
              </RailLinkButton>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-1 flex-col">
          <nav className="space-y-3" aria-label={t("sidebar.primaryNavigation", "Primary")}>
            <SidebarSection title={t("sidebar.section.research", "Research")}>
              <SidebarNavLink
                href={buildHomeHref()}
                label={analysisLabel}
                meta={t("sidebar.meta.analysis", "Reports and search")}
                active={isAnalysisActive}
                onClick={handleNavSelection}
              >
                <AnalysisIcon />
              </SidebarNavLink>
              <SidebarNavLink
                href={buildMarketBriefHref()}
                label={marketBriefLabel}
                meta={t("sidebar.meta.marketBrief", "Daily market briefs")}
                active={isMarketBriefActive}
                onClick={handleNavSelection}
              >
                <Newspaper className="h-4 w-4" aria-hidden />
              </SidebarNavLink>
              <SidebarNavLink
                href={buildScreenerHref()}
                label={screenerLabel}
                meta={t("sidebar.meta.screener", "Runs and candidates")}
                active={isScreenerActive}
                onClick={handleNavSelection}
              >
                <ScreenerIcon />
              </SidebarNavLink>
              {canAccessOpportunityRadar ? (
                <SidebarNavLink
                  href={buildOpportunitiesHref()}
                  label={opportunityLabel}
                  meta={t("sidebar.meta.opportunities", "Radar and watchlist")}
                  active={isOpportunityActive}
                  onClick={handleNavSelection}
                >
                  <Radar className="h-4 w-4" aria-hidden />
                </SidebarNavLink>
              ) : null}
            </SidebarSection>

            <SidebarSection title={t("sidebar.section.portfolio", "Portfolio")}>
              <SidebarNavLink
                href={buildAssetsHref()}
                label={assetsLabel}
                meta={t("sidebar.meta.assets", "Ledger and exposure")}
                active={isAssetsActive}
                onClick={handleNavSelection}
              >
                <AssetsIcon />
              </SidebarNavLink>
              <SidebarNavLink
                href={buildJournalHref()}
                label={journalLabel}
                meta={t("sidebar.meta.journal", "Trade review")}
                active={isJournalActive}
                onClick={handleNavSelection}
              >
                <JournalIcon />
              </SidebarNavLink>
            </SidebarSection>
          </nav>

          <div className="mt-auto mb-4 border-t border-[var(--border)] pt-2.5">
            <SidebarSectionHeading title={t("sidebar.section.operations", "Operations")} muted />
            <SidebarUtilityLink
              href={buildActivityHref()}
              label={activityLabel}
              meta={
                totalActive > 0
                  ? t("sidebar.activeCount", ({ count }) => `${count} active`, {
                      count: totalActive,
                    })
                  : t("sidebar.noActiveWork", "No active background work")
              }
              active={isActivityActive}
              badge={totalActive > 0 ? `${totalActive}` : null}
              onClick={handleNavSelection}
            >
              <ActivityIcon />
            </SidebarUtilityLink>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <>
      {isMobileViewport ? (
        <Sheet open={isMobileDrawerOpen} onOpenChange={(open) => !open && onClose()}>
          <SheetContent side="left" className="sidebar-surface sidebar-surface--quiet w-full max-w-xs border-r px-4 py-4 md:hidden [&>button]:hidden">
            <SheetHeader className="sr-only">
              <SheetTitle>{workbenchNavigationLabel}</SheetTitle>
            </SheetHeader>
            {sidebarBody}
          </SheetContent>
        </Sheet>
      ) : null}

      <div className={desktopShellClasses}>
        <aside
          id="report-navigation"
          className={desktopDrawerClasses}
          aria-label={workbenchNavigationLabel}
        >
          {sidebarBody}
        </aside>
      </div>
    </>
  );
}

function SidebarSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <SidebarSectionHeading title={title} />
      <div className="mt-1 space-y-1">{children}</div>
    </section>
  );
}

function SidebarSectionHeading({
  title,
  muted = false,
}: {
  title: string;
  muted?: boolean;
}) {
  return (
    <div
      className={`px-1.5 text-[9px] font-bold uppercase tracking-[0.14em] text-muted-foreground ${
        muted ? "opacity-75" : ""
      }`}
    >
      {title}
    </div>
  );
}

function SidebarNavLink({
  href,
  label,
  meta,
  active = false,
  onClick,
  children,
}: {
  href: string;
  label: string;
  meta: string;
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      data-active={active}
      className={`sidebar-nav-link focus-ring group flex items-center gap-2 rounded-md border px-2 py-1.5 transition ${
        active
          ? "border-[var(--border-strong)] bg-[var(--surface)] text-[var(--text)]"
          : "border-transparent bg-[var(--surface-translucent)] text-foreground hover:border-[var(--border)] hover:bg-[color:var(--surface-hover)]"
      }`}
      onClick={onClick}
    >
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md border ${
          active
            ? "border-[var(--accent-border)] bg-[var(--surface-translucent-strong)] text-[var(--primary-strong)]"
            : "border-[var(--border)] bg-[var(--surface-translucent)] text-muted-foreground"
        }`}
      >
        {children}
      </div>
      <div className="min-w-0">
        <div className="block text-[12px] font-bold leading-4">{label}</div>
        <div className="block text-[10px] leading-3.5 text-muted-foreground">{meta}</div>
      </div>
    </Link>
  );
}

function SidebarUtilityLink({
  href,
  label,
  meta,
  badge,
  active = false,
  onClick,
  children,
}: {
  href: string;
  label: string;
  meta: string;
  badge?: string | null;
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      data-active={active}
      className={`sidebar-utility-link focus-ring flex items-center justify-between gap-2 rounded-md border px-2 py-1.5 transition ${
        active
          ? "border-[var(--border-strong)] bg-[var(--surface)] text-[var(--text)]"
          : "border-[var(--border)] bg-[var(--surface-translucent)] text-foreground hover:border-[var(--border-strong)] hover:bg-[color:var(--surface-hover)]"
      }`}
      onClick={onClick}
    >
      <div className="flex min-w-0 items-center gap-2">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--surface-translucent)] text-muted-foreground">
          {children}
        </div>
        <div className="min-w-0">
          <div className="block text-[12px] font-bold leading-4">{label}</div>
          <div className="block truncate text-[10px] leading-3.5 text-muted-foreground">{meta}</div>
        </div>
      </div>
      {badge ? (
        <span className="shrink-0 rounded bg-[var(--primary)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--primary-foreground)]">
          {badge}
        </span>
      ) : null}
    </Link>
  );
}

function RailLinkButton({
  href,
  label,
  title,
  active = false,
  count,
  onClick,
  children,
}: {
  href: string;
  label: string;
  title: string;
  active?: boolean;
  count?: number;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      data-active={active}
      title={title}
      aria-label={label}
      onClick={onClick}
      className={`sidebar-rail-link relative inline-flex h-9 w-9 items-center justify-center rounded-md border transition ${
        active
          ? "border-[var(--border-strong)] bg-[var(--surface)] text-[var(--text)]"
          : "border-[var(--border)] bg-[var(--surface-translucent)] text-muted-foreground hover:border-[var(--primary)] hover:bg-[color:var(--surface-hover)] hover:text-[var(--primary)]"
      }`}
    >
      {children}
      {typeof count === "number" && count > 0 ? (
        <span className="absolute -right-1 -top-1 rounded bg-[var(--primary)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--primary-foreground)]">
          {count}
        </span>
      ) : null}
    </Link>
  );
}

function AnalysisIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
      <path
        d="M4.75 14.25 8 10.5l2.25 2.25L15.25 6.5"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4.75 4.75h10.5v10.5H4.75z"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
}

function ScreenerIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
      <rect x="4" y="4" width="12" height="12" rx="3" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M7 7.5h6M7 10h6M7 12.5h4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function AssetsIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
      <path
        d="M4.5 6.5h11M4.5 10h11M4.5 13.5h11"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <rect
        x="3.75"
        y="4.75"
        width="12.5"
        height="10.5"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
}

function JournalIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
      <path
        d="M6 4.75h7.5A1.75 1.75 0 0 1 15.25 6.5v8.75H6A1.75 1.75 0 0 0 4.25 17V6.5A1.75 1.75 0 0 1 6 4.75Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M7.5 8.25h4.5M7.5 11h4.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ActivityIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
      <path
        d="M4.5 10h2.75l1.5-3 2.5 6 1.5-3H15.5"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect
        x="3.75"
        y="4.75"
        width="12.5"
        height="10.5"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
}
