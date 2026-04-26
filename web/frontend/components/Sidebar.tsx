"use client";

import Link from "next/link";
import {
  type ReactNode,
  useEffect,
  useState,
} from "react";
import { usePathname } from "next/navigation";
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
  const { activeScreenerTasks, activeTasks } = useWorkbench();
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
  const totalActive = activeTasks.length + activeScreenerTasks.length;
  const analysisLabel = t("sidebar.nav.analysis", "Analysis");
  const screenerLabel = t("sidebar.nav.screener", "Screener");
  const assetsLabel = t("sidebar.nav.assets", "Assets");
  const journalLabel = t("sidebar.nav.journal", "Journal");
  const activityLabel = t("sidebar.nav.activity", "Activity");
  const workbenchNavigationLabel = t(
    "sidebar.workbenchNavigation",
    "Workbench navigation"
  );
  const isAnalysisActive = pathname === "/" || pathname.startsWith("/reports/");
  const isScreenerActive =
    pathname === buildScreenerHref() || pathname.startsWith("/screeners/");
  const isAssetsActive =
    pathname === buildAssetsHref() || pathname.startsWith("/assets/");
  const isJournalActive = pathname === buildJournalHref();
  const isActivityActive =
    pathname === buildActivityHref() ||
    pathname.startsWith("/tasks/") ||
    pathname.startsWith("/screener-tasks/");

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
    "sidebar-surface hidden flex-col overflow-y-auto border-r border-[var(--border)] py-5 transition-[width,padding] duration-300 md:flex",
    isDesktopCollapsed
      ? "md:w-[5.5rem] md:max-w-none md:px-3"
      : "md:w-[18rem] md:max-w-none md:px-4",
    "md:relative md:h-full md:border-r-0",
  ].join(" ");
  const desktopShellClasses = [
    "md:sticky md:top-0 md:flex md:h-[100svh] md:self-start md:shrink-0 md:overflow-visible",
    isDesktopCollapsed ? "md:w-[5.5rem]" : "md:w-[18rem]",
  ].join(" ");
  const headerClasses = [
    "border-b border-[var(--border)] pb-4",
    isDesktopRail ? "flex justify-center" : "flex items-center",
  ].join(" ");

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
        <Link href={buildHomeHref()} className="flex min-w-0 items-center gap-3">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--primary)] shadow-[0_10px_20px_rgba(28,36,48,0.08)]">
            <DivergeMark className="h-9 w-9" />
          </div>
          {!isDesktopRail ? (
            <div className="min-w-0">
              <p className="font-heading text-lg font-semibold text-slate-900">Diverge</p>
            </div>
          ) : null}
        </Link>

        {isMobileViewport ? (
          <Button
            type="button"
            variant="secondary"
            size="icon"
            className="rounded-xl md:hidden"
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
      </div>

      {isDesktopRail ? (
        <div className="mt-5 flex flex-1 flex-col items-center">
          <div className="flex flex-col items-center gap-2">
            <div className="flex flex-col items-center gap-2">
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
                href={buildScreenerHref()}
                label={screenerLabel}
                title={screenerLabel}
                active={isScreenerActive}
                onClick={handleNavSelection}
              >
                <ScreenerIcon />
              </RailLinkButton>
            </div>

            <div className="my-2 flex justify-center" aria-hidden="true">
              <span className="h-px w-7 rounded-full bg-[rgba(28,56,83,0.12)]" />
            </div>

            <div className="flex flex-col items-center gap-2">
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

          <div className="mt-auto w-full border-t border-[var(--border)] pt-4">
            <div className="mb-3 flex justify-center" aria-hidden="true">
              <span className="h-5 w-px rounded-full bg-gradient-to-b from-[rgba(28,56,83,0.16)] to-transparent" />
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
        <div className="mt-5 flex flex-1 flex-col">
          <nav className="space-y-4" aria-label={t("sidebar.primaryNavigation", "Primary")}>
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
                href={buildScreenerHref()}
                label={screenerLabel}
                meta={t("sidebar.meta.screener", "Runs and candidates")}
                active={isScreenerActive}
                onClick={handleNavSelection}
              >
                <ScreenerIcon />
              </SidebarNavLink>
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

          <div className="mt-auto border-t border-[var(--border)] pt-4">
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
          <SheetContent side="left" className="sidebar-surface w-full max-w-xs border-r px-4 py-5 md:hidden [&>button]:hidden">
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

        <div className="pointer-events-none absolute left-full top-1/2 z-[60] hidden -translate-y-1/2 md:flex">
          <div className="pointer-events-auto -translate-x-[64%]">
            <DesktopUtilityControl
              isDesktopRail={isDesktopRail}
              onToggle={toggleDesktopCollapse}
              expandLabel={t("sidebar.expand", "Expand sidebar")}
              collapseLabel={t("sidebar.collapse", "Collapse sidebar")}
            />
          </div>
        </div>
      </div>
    </>
  );
}

function DesktopUtilityControl({
  isDesktopRail,
  onToggle,
  expandLabel,
  collapseLabel,
}: {
  isDesktopRail: boolean;
  onToggle: () => void;
  expandLabel: string;
  collapseLabel: string;
}) {
  const label = isDesktopRail ? expandLabel : collapseLabel;

  return (
    <button
      type="button"
      className="focus-ring inline-flex h-14 w-6 items-center justify-center rounded-full border border-[rgba(28,56,83,0.12)] bg-white/95 text-slate-500 shadow-[0_12px_24px_rgba(18,28,41,0.08)] transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)] hover:text-[var(--primary)]"
      onClick={onToggle}
      aria-label={label}
      aria-expanded={!isDesktopRail}
      title={label}
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
      <div className="mt-2 space-y-1.5">{children}</div>
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
      className={`px-2 text-[11px] font-semibold uppercase tracking-[0.24em] ${
        muted ? "text-slate-400" : "text-slate-500"
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
      className={`focus-ring group flex items-center gap-3 rounded-[20px] border px-3 py-3 transition ${
        active
          ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-[0_14px_30px_rgba(28,36,48,0.1)]"
          : "border-transparent bg-white/68 text-slate-700 hover:border-[var(--border)] hover:bg-white"
      }`}
      onClick={onClick}
    >
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border ${
          active
            ? "border-[rgba(93,116,112,0.24)] bg-white text-[var(--primary-strong)]"
            : "border-[var(--border)] bg-white text-slate-500"
        }`}
      >
        {children}
      </div>
      <div className="min-w-0">
        <div className="block text-sm font-semibold">{label}</div>
        <div className="mt-0.5 block text-xs text-slate-500">{meta}</div>
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
      className={`focus-ring flex items-center justify-between gap-3 rounded-[20px] border px-3 py-3 transition ${
        active
          ? "border-[var(--accent)] bg-[var(--accent-soft)] text-slate-900"
          : "border-[var(--border)] bg-white/76 text-slate-700 hover:border-[var(--border-strong)] hover:bg-white"
      }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[var(--border)] bg-white text-slate-500">
          {children}
        </div>
        <div>
          <div className="block text-sm font-semibold">{label}</div>
          <div className="mt-0.5 block text-xs text-slate-500">{meta}</div>
        </div>
      </div>
      {badge ? (
        <span className="rounded-full bg-[var(--accent)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-white">
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
      title={title}
      aria-label={label}
      onClick={onClick}
      className={`relative inline-flex h-11 w-11 items-center justify-center rounded-2xl border transition ${
        active
          ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
          : "border-[var(--border)] bg-white text-slate-600 hover:border-[var(--primary)] hover:text-[var(--primary)]"
      }`}
    >
      {children}
      {typeof count === "number" && count > 0 ? (
        <span className="absolute -right-1 -top-1 rounded-full bg-[var(--accent)] px-1.5 py-0.5 text-[10px] font-semibold text-white">
          {count}
        </span>
      ) : null}
    </Link>
  );
}

function AnalysisIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" aria-hidden>
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
    <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" aria-hidden>
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
    <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" aria-hidden>
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
    <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" aria-hidden>
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
    <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" aria-hidden>
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
